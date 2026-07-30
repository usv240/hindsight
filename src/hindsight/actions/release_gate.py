"""A DataHub Action that audits an exact-bound model when its metadata changes.

It subscribes to DataHub's metadata event stream and audits the configured ML
model without relying on a person to trigger the release check.

That is the difference between a tool and a gate. A release check nobody triggers
is a release check that does not happen.

Deploy in the isolated official runtime with:

    docker compose -f docker/hindsight-action.compose.yml up

The action does **not** publish governed evidence on its own. Incident notification
is optional; the proof deployment is observe-only, and a human still approves any
catalog write-back.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# The Actions framework is an optional, deployment-time dependency. Importing it
# at module scope would make the package unusable for anyone who only wants the
# CLI, so the base classes are resolved lazily and a stub is used otherwise.
try:  # pragma: no cover - exercised only in a real Actions deployment
    from datahub_actions.action.action import Action
    from datahub_actions.event.event_envelope import EventEnvelope
    from datahub_actions.pipeline.pipeline_context import PipelineContext

    ACTIONS_AVAILABLE = True
except ImportError:  # pragma: no cover
    ACTIONS_AVAILABLE = False

    class Action:  # type: ignore[no-redef]
        """Stub so the module imports without the Actions framework installed."""

    EventEnvelope = Any  # type: ignore[misc,assignment]
    PipelineContext = Any  # type: ignore[misc,assignment]


# Entity types worth auditing on creation.
WATCHED_ENTITY_TYPES = frozenset({"mlModel", "mlModelGroup", "dataset"})


class HindsightReleaseGate(Action):
    """Audit exact-bound model changes and record what was found.

    Configuration (from the pipeline YAML):

    ``audit``
        Path to the audit config describing what to run. Defaults to the
        repository's own credit-default audit.
    ``target_urn``
        Exact model URN this Action is permitted to audit.
    ``entity_types``
        Which entity types to react to. Defaults to ML models.
    ``raise_incident``
        Whether to raise a DataHub incident when a release is blocked.
        Defaults to true; the incident is a notification, never an approval.
    ``proof_log_path``
        Optional append-only JSONL path for machine-readable local results.
    ``project_root``
        Where scenarios and audit configs live. Defaults to the process CWD.
    """

    def __init__(self, config: dict[str, Any], ctx: PipelineContext) -> None:
        self.config = config or {}
        self.ctx = ctx
        self.project_root = Path(self.config.get("project_root", Path.cwd()))
        self.audit_path = self.config.get("audit", "audits/credit_default.json")
        self.entity_types = frozenset(
            self.config.get("entity_types", ["mlModel"]) or WATCHED_ENTITY_TYPES
        )
        self.raise_incident = bool(self.config.get("raise_incident", True))
        self.target_urn = self.config.get("target_urn")
        self.audited: list[dict[str, Any]] = []
        self._seen_events: set[str] = set()

    @classmethod
    def create(cls, config_dict: dict[str, Any], ctx: PipelineContext) -> HindsightReleaseGate:
        return cls(config_dict or {}, ctx)

    # -- event handling ----------------------------------------------------

    def act(self, event: EventEnvelope) -> None:
        urn, entity_type = self._extract(event)
        if not urn:
            return
        logger.info(
            "Hindsight: event observed urn=%s entity_type=%s bound_target=%s",
            urn,
            entity_type,
            self.target_urn or "<audit-config>",
        )
        if entity_type and entity_type not in self.entity_types:
            logger.debug("Hindsight: ignoring %s (%s)", urn, entity_type)
            return
        if self.target_urn and urn != self.target_urn:
            logger.debug("Hindsight: ignoring unbound asset %s", urn)
            return

        event_key = self._event_key(event, urn)
        if event_key in self._seen_events:
            logger.debug("Hindsight: ignoring an exact redelivery for %s", urn)
            return
        logger.info("Hindsight: auditing changed model %s", urn)
        try:
            result = self.audit(urn)
        except Exception:  # noqa: BLE001 - an action must never take the pipeline down
            logger.exception("Hindsight: audit failed for %s", urn)
            return

        self.audited.append(result)
        self._seen_events.add(event_key)
        self._record_proof(result)
        logger.info(
            "Hindsight: %s -> %s (%s)",
            urn,
            result["release_decision"],
            result["verdict"],
        )

    def audit(self, urn: str) -> dict[str, Any]:
        """Run the audit for one asset and return a compact result."""
        from hindsight.config import AuditConfig
        from hindsight.workflow import run_demo_audit

        config = AuditConfig.load(self.project_root / self.audit_path, self.project_root)
        configured_target = self.target_urn or config.target_urn
        if not configured_target:
            raise ValueError("DataHub Action requires an exact target_urn binding")
        if configured_target != urn:
            raise ValueError(f"Action is bound to {configured_target}, not incoming asset {urn}")
        bundle = run_demo_audit(
            scenario_path=config.scenario_path,
            transformation_path=config.transformation_path,
            remediation_path=config.remediation_path,
            post_outcome_table=config.post_outcome_table,
            available_column=config.available_column,
            prediction_column=config.prediction_column,
            subject=config.subject,
        )
        evidence_model_urn = bundle["validation"]["evidence_context"]["leakage_model_urn"]
        if evidence_model_urn != configured_target:
            raise ValueError(
                "Audit evidence describes "
                f"{evidence_model_urn}, not bound model {configured_target}"
            )
        result = {
            "urn": urn,
            "evidence_model_urn": evidence_model_urn,
            "audit": config.name,
            "verdict": bundle["verdict"],
            "release_decision": bundle["release_decision"],
            "confirmation_route": bundle["confirmation_route"],
            "exit_code": bundle["exit_code"],
            "incident_raised": False,
        }

        if self.raise_incident and bundle["release_decision"] == "block":
            result["incident_raised"] = self._raise_incident(urn, bundle)
        return result

    def _raise_incident(self, urn: str, bundle: dict[str, Any]) -> bool:
        """Notify, do not mutate. A human still approves the full write-back."""
        try:
            from hindsight.writeback.datahub import raise_leakage_incident

            raise_leakage_incident(
                self.config.get("server", "http://localhost:8080"),
                self.config.get("token"),
                urn,
                case_id=bundle["case_id"],
                document_urn="(raised automatically by the Hindsight release gate)",
            )
            return True
        except Exception:  # noqa: BLE001
            logger.exception("Hindsight: could not raise an incident for %s", urn)
            return False

    def close(self) -> None:
        blocked = sum(1 for r in self.audited if r["release_decision"] == "block")
        logger.info(
            "Hindsight release gate stopping: %d audited, %d blocked",
            len(self.audited),
            blocked,
        )

    def _record_proof(self, result: dict[str, Any]) -> None:
        """Append a machine-readable local proof when explicitly configured."""
        proof_path = self.config.get("proof_log_path")
        if not proof_path:
            return
        path = Path(proof_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(result, sort_keys=True) + "\n")

    @staticmethod
    def _event_key(event: Any, urn: str) -> str:
        """Stable identity for one Kafka delivery, without suppressing later changes."""
        payload = getattr(event, "event", event)
        if hasattr(payload, "as_json"):
            body = payload.as_json()
        elif isinstance(payload, str):
            body = payload
        else:
            body = json.dumps(payload, sort_keys=True, default=str)
        material = json.dumps(
            {"urn": urn, "event": body, "meta": getattr(event, "meta", None)},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(material.encode()).hexdigest()

    # -- event parsing -----------------------------------------------------

    @staticmethod
    def _extract(event: Any) -> tuple[str | None, str | None]:
        """Pull the URN and entity type out of an event envelope.

        Handles both `EntityChangeEvent_v1` and `MetadataChangeLogEvent_v1`, and
        tolerates a plain dict so the logic is testable without Kafka.
        """
        payload = getattr(event, "event", event)

        urn = _get(payload, "entityUrn") or _get(payload, "urn")
        entity_type = _get(payload, "entityType")

        if not urn and isinstance(payload, str):
            try:
                decoded = json.loads(payload)
            except (TypeError, ValueError):
                return None, None
            urn = decoded.get("entityUrn") or decoded.get("urn")
            entity_type = decoded.get("entityType")

        # Fall back to reading the type out of the URN itself.
        if urn and not entity_type and urn.startswith("urn:li:"):
            parts = urn.split(":", 3)
            entity_type = parts[2] if len(parts) > 2 else None

        return urn, entity_type


def _get(payload: Any, key: str) -> str | None:
    value = payload.get(key) if isinstance(payload, dict) else getattr(payload, key, None)
    return value if isinstance(value, str) else None
