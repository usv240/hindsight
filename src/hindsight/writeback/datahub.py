from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from hindsight.phase0.writeback_probe import (
    PROPERTY_URN,
    _ensure_structured_property,
    _get_incidents_with_retry,
    _graphql,
    _has_property,
)

TAG_NAME = "hindsight:leakage-confirmed"
TAG_DISPLAY_NAME = "Hindsight leakage confirmed"


def publish_audit(
    bundle: dict[str, Any],
    *,
    target_urn: str,
    server: str,
    token: str | None = None,
    approved: bool = False,
) -> dict[str, Any]:
    """Publish one verified audit bundle, but only with explicit approval."""
    if not approved:
        return {
            "schema_version": 1,
            "status": "awaiting_human_approval",
            "target_urn": target_urn,
            "case_id": bundle["case_id"],
            "planned_types": bundle["writeback"]["planned_types"],
            "mutation_performed": False,
        }
    if bundle.get("release_decision") != "block" or bundle.get("verdict") != "confirmed":
        raise ValueError("Only a deterministic confirmed/block bundle can use this publisher")

    from datahub.metadata.urns import TagUrn
    from datahub.sdk import DataHubClient, Document, Tag

    client = DataHubClient(server=server, token=token)
    client.test_connection()
    target = client.entities.get(target_urn)

    client.entities.upsert(
        Tag(
            name=TAG_NAME,
            display_name=TAG_DISPLAY_NAME,
            description="Approved Hindsight evidence confirms ML target or temporal leakage.",
        )
    )
    field = next(
        (
            item
            for item in (getattr(target, "schema", None) or [])
            if item.field_path == "days_since_last_payment"
        ),
        None,
    )
    if field is None:
        raise ValueError(f"Target {target_urn} lacks days_since_last_payment schema metadata")
    field.add_tag(TagUrn(TAG_NAME))

    _ensure_structured_property(server, token)
    target.set_structured_property(PROPERTY_URN, [bundle["verdict"]])
    client.entities.upsert(target)

    document = Document.create_document(
        id=_document_id(bundle["case_id"]),
        title=f"Hindsight audit: {bundle['case_id']}",
        text=_render_document(bundle),
        subtype="ML Leakage Audit",
        related_assets=[target_urn],
        custom_properties={
            "hindsight_case_id": bundle["case_id"],
            "hindsight_verdict": bundle["verdict"],
            "hindsight_release_decision": bundle["release_decision"],
            "scenario_config_sha256": bundle["validation"]["config_sha256"],
        },
        show_in_global_context=False,
    )
    client.entities.upsert(document)
    incident_urn = _find_or_raise_incident(
        server,
        token,
        target_urn,
        case_id=bundle["case_id"],
        document_urn=str(document.urn),
    )

    reread_target = client.entities.get(target_urn)
    reread_field = next(
        item for item in reread_target.schema if item.field_path == "days_since_last_payment"
    )
    reread_document = client.entities.get(document.urn)
    incidents = _get_incidents_with_retry(server, token, target_urn)
    checks = {
        "confirmed_field_tag_reread": str(TagUrn(TAG_NAME))
        in {str(association.tag) for association in reread_field.tags},
        "confirmed_structured_property_reread": _has_property(
            reread_target.structured_properties, PROPERTY_URN, "confirmed"
        ),
        "audit_document_reread": (
            reread_document.title == document.title
            and target_urn in (reread_document.related_assets or [])
        ),
        "active_incident_reread": any(
            incident.get("urn") == incident_urn
            and incident.get("status", {}).get("state") == "ACTIVE"
            for incident in incidents
        ),
    }
    return {
        "schema_version": 1,
        "captured_at": datetime.now(UTC).isoformat(),
        "status": "published" if all(checks.values()) else "verification_failed",
        "server": server,
        "target_urn": target_urn,
        "case_id": bundle["case_id"],
        "verdict": bundle["verdict"],
        "release_decision": bundle["release_decision"],
        "checks": checks,
        "entities": {
            "tag": str(TagUrn(TAG_NAME)),
            "structured_property": PROPERTY_URN,
            "document": str(document.urn),
            "incident": incident_urn,
        },
        "mutation_performed": True,
    }


def _document_id(case_id: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", case_id).strip("-")
    return f"hindsight-audit-{normalized}"


def _render_document(bundle: dict[str, Any]) -> str:
    leakage = bundle["validation"]["leakage_case"]
    safe = bundle["validation"]["safe_control"]
    predicate = bundle["remediation"]["verification"]["cutoff_predicates"][0]
    return (
        f"# Hindsight audit: {bundle['case_id']}\n\n"
        f"**Release decision:** {bundle['release_decision'].upper()}  \n"
        f"**Verdict:** `{bundle['verdict']}`\n\n"
        "## Point-in-time evidence\n\n"
        f"Observed AUC: `{leakage['observed_auc']}`  \n"
        f"Reconstructed AUC: `{leakage['point_in_time_auc']}`  \n"
        f"Post-cutoff records excluded: "
        f"`{bundle['validation']['reconstruction']['excluded_post_cutoff_records']}`\n\n"
        "## Safe control\n\n"
        f"Ablation delta: `{safe['observed_advantage']}`  \n"
        f"Advantage retained: `{safe['advantage_retained']}`\n\n"
        "## Approved remediation proposal\n\n"
        f"```sql\n{predicate}\n```\n\n"
        f"Evidence bundle summary:\n```json\n{json.dumps(bundle['checks'], indent=2)}\n```"
    )


def _find_or_raise_incident(
    server: str,
    token: str | None,
    target_urn: str,
    *,
    case_id: str,
    document_urn: str,
) -> str:
    title = f"Hindsight release blocked: {case_id}"
    for incident in _get_incidents_with_retry(server, token, target_urn):
        if incident.get("title") == title:
            return str(incident["urn"])

    data = _graphql(
        server,
        token,
        """
          mutation RaiseIncident($input: RaiseIncidentInput!) {
            raiseIncident(input: $input)
          }
        """,
        {
            "input": {
                "resourceUrn": target_urn,
                "type": "CUSTOM",
                "customType": "ML_LEAKAGE",
                "title": title,
                "description": (f"Approved Hindsight audit {case_id}. Evidence: {document_urn}"),
            }
        },
    )
    incident_urn = data.get("raiseIncident")
    if not isinstance(incident_urn, str):
        raise RuntimeError(f"DataHub did not return an incident URN: {data}")
    return incident_urn
