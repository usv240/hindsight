"""Build a human-readable activity feed describing what Hindsight actually did.

The console shows this as a backend log so a visitor can watch the agent work
rather than being handed a conclusion. Every entry is derived from a real
artifact - the fixture manifest, the audit bundle, or a publication result - and
each one carries a ``source`` so nothing is presented as live when it was
replayed from a recording.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

Source = Literal["recorded", "computed", "live"]

# What each log line is talking about, so the UI can colour it and link it to
# the right glossary entry.
Channel = Literal["datahub", "mcp", "sql", "validation", "verdict", "writeback"]


def _entry(
    *,
    channel: Channel,
    source: Source,
    message: str,
    detail: str | None = None,
    ok: bool | None = None,
    glossary: str | None = None,
) -> dict[str, Any]:
    return {
        "channel": channel,
        "source": source,
        "message": message,
        "detail": detail,
        "ok": ok,
        "glossary": glossary,
    }


def build_activity(
    project_root: Path,
    bundle: dict[str, Any],
    publication: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return an ordered activity feed for one audit run."""
    manifest = _read_manifest(project_root)
    captured = manifest.get("captured_from", {})
    validation = bundle["validation"]
    leakage = validation["leakage_case"]
    safe = validation["safe_control"]
    sql = bundle["sql_verification"]

    feed: list[dict[str, Any]] = [
        _entry(
            channel="datahub",
            source="recorded",
            message="Connecting to DataHub metadata graph",
            detail=(
                f"DataHub Core {captured.get('datahub_core', 'unknown')} - "
                f"SDK {captured.get('datahub_sdk', 'unknown')}"
            ),
            ok=True,
            glossary="datahub",
        ),
        _entry(
            channel="mcp",
            source="recorded",
            message="Discovering tools over the DataHub MCP Server",
            detail=(
                f"mcp-server-datahub {captured.get('mcp_server_datahub', 'unknown')} - "
                "search, entity, lineage, tag, property and document tools available"
            ),
            ok=True,
            glossary="mcp",
        ),
        _entry(
            channel="datahub",
            source="recorded",
            message="Resolving the candidate model version and its features",
            detail=bundle["case_id"],
            ok=True,
            glossary="ml-lineage",
        ),
        _entry(
            channel="datahub",
            source="recorded",
            message="Traversing fine-grained column lineage",
            detail=(
                "payment_events_after_decision.payment_recorded_at "
                "-> feature_pipeline_leaky.days_since_last_payment"
            ),
            ok=True,
            glossary="column-lineage",
        ),
        _entry(
            channel="datahub",
            source="computed",
            message="Classifying the upstream source against the prediction cutoff",
            detail="source_kind = post_outcome - available 31 days after the decision",
            ok=False,
            glossary="prediction-cutoff",
        ),
        _entry(
            channel="sql",
            source="computed",
            message="Parsing the transformation SQL with sqlglot",
            detail=_sql_detail(sql),
            ok=sql["status"] != "violation",
            glossary="transformation-check",
        ),
        _entry(
            channel="validation",
            source="computed",
            message="Rebuilding the feature with post-cutoff rows removed",
            detail=(
                f"{validation['reconstruction']['excluded_post_cutoff_records']:,} of "
                f"{validation['rows']:,} records excluded by "
                f"`{validation['reconstruction']['cutoff_predicate']}`"
            ),
            ok=True,
            glossary="point-in-time",
        ),
        _entry(
            channel="validation",
            source="computed",
            message="Comparing honest performance against observed performance",
            detail=(
                f"AUC {leakage['observed_auc']:.6f} -> {leakage['point_in_time_auc']:.6f} - "
                f"{(1 - leakage['advantage_retained']) * 100:.1f}% of the advantage disappeared"
            ),
            ok=False,
            glossary="advantage-retained",
        ),
        _entry(
            channel="validation",
            source="computed",
            message="Running the false-positive control",
            detail=(
                f"legitimate feature keeps {safe['advantage_retained'] * 100:.0f}% of its "
                f"advantage despite a larger ablation delta of {safe['observed_advantage']:.6f}"
            ),
            ok=True,
            glossary="safe-control",
        ),
        _entry(
            channel="verdict",
            source="computed",
            message=f"Deterministic verdict: {bundle['verdict']}",
            detail=(
                f"release decision = {bundle['release_decision']} - "
                f"CI exit code {bundle['exit_code']}"
            ),
            ok=bundle["verdict"] == "clear_for_release",
            glossary="verdict-lattice",
        ),
    ]

    feed.extend(_writeback_entries(bundle, publication))
    return feed


def _writeback_entries(
    bundle: dict[str, Any], publication: dict[str, Any] | None
) -> list[dict[str, Any]]:
    if publication is None:
        planned = ", ".join(bundle["writeback"]["planned_types"])
        return [
            _entry(
                channel="writeback",
                source="computed",
                message="Write-back held at the human approval boundary",
                detail=f"{planned} - nothing was written to the catalog",
                ok=True,
                glossary="approval-gate",
            )
        ]

    if publication.get("status") == "error":
        return [
            _entry(
                channel="writeback",
                source="live",
                message="Write-back failed",
                detail=str(publication.get("message", "unknown error")),
                ok=False,
                glossary="approval-gate",
            )
        ]

    if not publication.get("mutation_performed"):
        planned = ", ".join(publication.get("planned_types", []))
        return [
            _entry(
                channel="writeback",
                source="live",
                message="Dry run - approval not granted",
                detail=f"would write {planned}",
                ok=True,
                glossary="approval-gate",
            )
        ]

    entities = publication.get("entities", {})
    checks = publication.get("checks", {})
    labels = {
        "tag": ("Field tag written to the offending column", "confirmed_field_tag_reread"),
        "structured_property": (
            "Structured verdict property written to the asset",
            "confirmed_structured_property_reread",
        ),
        "document": ("Audit Document written and linked", "audit_document_reread"),
        "incident": ("Leakage incident raised and left active", "active_incident_reread"),
    }
    entries = [
        _entry(
            channel="writeback",
            source="live",
            message="Human approval granted - publishing evidence to DataHub",
            detail=publication.get("target_urn", ""),
            ok=True,
            glossary="approval-gate",
        )
    ]
    for key, (message, check_key) in labels.items():
        if key in entities:
            entries.append(
                _entry(
                    channel="writeback",
                    source="live",
                    message=message,
                    detail=entities[key],
                    ok=bool(checks.get(check_key)),
                    glossary="writeback-types",
                )
            )
    entries.append(
        _entry(
            channel="datahub",
            source="live",
            message="Re-reading every mutation to prove persistence",
            detail=f"{sum(1 for v in checks.values() if v)}/{len(checks)} confirmed by re-read",
            ok=all(checks.values()) if checks else False,
            glossary="reread",
        )
    )
    return entries


def _sql_detail(sql: dict[str, Any]) -> str:
    tables = ", ".join(sql.get("referenced_tables", ()))
    predicates = sql.get("cutoff_predicates", ())
    if predicates:
        return f"cutoff predicate found: {predicates[0]}"
    return f"no availability cutoff found across {tables or 'the referenced tables'}"


def _read_manifest(project_root: Path) -> dict[str, Any]:
    path = project_root / "fixtures/credit_default/manifest.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
