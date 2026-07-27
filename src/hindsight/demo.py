from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hindsight.engine import audit_case
from hindsight.fixtures import run_fixture_replay
from hindsight.models import AuditCase


def run_judge_demo(project_root: Path) -> dict[str, Any]:
    """Run the fastest complete judge story with unsafe and safe cases side by side."""
    examples = project_root / "examples"
    leaked_payload = json.loads(
        (examples / "confirmed_leakage.case.json").read_text(encoding="utf-8")
    )
    safe_payload = json.loads(
        (examples / "high_correlation_safe.case.json").read_text(encoding="utf-8")
    )
    leaked = audit_case(AuditCase.from_dict(leaked_payload))
    safe = audit_case(AuditCase.from_dict(safe_payload))
    replay = run_fixture_replay(project_root / "fixtures/credit_default")
    manifest = json.loads(
        (project_root / "fixtures/credit_default/manifest.json").read_text(encoding="utf-8")
    )
    leaked_delta = float(leaked_payload["ablation_delta"])
    safe_delta = float(safe_payload["ablation_delta"])
    checks = {
        "deterministic_leakage_fixture_confirmed": leaked.verdict.value == "confirmed",
        "high_correlation_control_cleared": safe.verdict.value == "clear_for_release",
        "safe_ablation_delta_exceeds_leaked_delta": safe_delta > leaked_delta,
        "point_in_time_fixture_replay_passed": replay["status"] == "passed",
        "point_in_time_route_confirmed": (
            replay.get("verdicts", {}).get("leakage_case", {}).get("verdict") == "confirmed"
        ),
    }
    return {
        "schema_version": 1,
        "status": "passed" if all(checks.values()) else "failed",
        "headline": "An ablation-only detector gets this exactly backwards.",
        "checks": checks,
        "datahub_evidence": {
            "why_datahub_is_required": (
                "Leakage is a cross-system, column-level defect. The notebook cannot see it "
                "because the leak happened upstream in the warehouse; the feature store sees "
                "features but not their ancestry; model monitoring fires months later. Only a "
                "column-level lineage graph makes the question answerable before release."
            ),
            "feature_urn": leaked_payload["feature_urn"],
            "model_urn": leaked_payload["model_urn"],
            "column_lineage_path": list(leaked.evidence["lineage_path"]),
            "source_kind": leaked.evidence["source_kind"],
            "recorded_from": manifest.get("captured_from", {}),
            "captured_at": manifest.get("captured_at"),
            "reprove_command": "hindsight verify-fixture-live",
            "live_path_writes_back": [
                "hindsight:leakage-confirmed field tag",
                "hindsight.auditVerdict structured property",
                "linked audit Document",
                "active ML_LEAKAGE incident",
            ],
        },
        "deterministic_proof_fixture": {
            "case_id": leaked.case_id,
            "verdict": leaked.verdict.value,
            "ablation_delta": leaked_delta,
            "confirmation_route": "deterministic_cutoff_proof",
        },
        "safe_control": {
            "case_id": safe.case_id,
            "verdict": safe.verdict.value,
            "ablation_delta": safe_delta,
            "confirmation_route": "pre_outcome_lineage_and_availability",
        },
        "ablation_contrast": {
            "leaked_feature": leaked_delta,
            "safe_feature": safe_delta,
            "safe_exceeds_leaked_by": round(safe_delta - leaked_delta, 6),
            "conclusion": (
                "The legitimate feature has the larger ablation delta, yet Hindsight clears it."
            ),
        },
        "point_in_time_proof_fixture": {
            "fixture_id": replay.get("fixture_id"),
            "status": replay["status"],
            "verdict": replay.get("verdicts", {}).get("leakage_case", {}).get("verdict"),
            "observed_auc": replay.get("recorded_validation", {})
            .get("leakage_case", {})
            .get("observed_auc"),
            "point_in_time_auc": replay.get("recorded_validation", {})
            .get("leakage_case", {})
            .get("point_in_time_auc"),
            "advantage_retained": replay.get("recorded_validation", {})
            .get("leakage_case", {})
            .get("advantage_retained"),
            "runtime_seconds": replay.get("runtime_seconds"),
        },
        "disclosures": [
            (
                "The deterministic example and point-in-time recording are independent "
                "confirmation routes for the same planted defect mechanism."
            ),
            (
                "The planted leak is total by construction, so observed AUC 1.000000 is "
                "expected; real-world leakage can be subtler."
            ),
            (
                "The 50% majority-loss threshold is a visible demo policy, not a universal "
                "scientific constant, and it cannot confirm leakage without directional "
                "post-outcome lineage plus an availability-time violation."
            ),
        ],
        "exit_code": 0 if all(checks.values()) else 2,
    }


def render_judge_demo(report: dict[str, Any]) -> str:
    leaked = report["deterministic_proof_fixture"]
    safe = report["safe_control"]
    point_in_time = report["point_in_time_proof_fixture"]
    dh = report["datahub_evidence"]
    captured = dh.get("recorded_from", {})
    lines = [
        "HINDSIGHT - GOLDEN DEMO",
        "=" * 25,
        "",
        "DATAHUB COLUMN LINEAGE (the evidence this verdict rests on)",
        *[
            f"  {'   ' if i else ''}{'-> ' if i else ''}{node}"
            for i, node in enumerate(dh["column_lineage_path"])
        ],
        f"  source classified as: {dh['source_kind']}",
        "",
        "  Recorded from live DataHub Core "
        f"{captured.get('datahub_core', '?')} via MCP server "
        f"{captured.get('mcp_server_datahub', '?')} on {dh.get('captured_at', '?')}.",
        f"  Re-prove against your own instance: {dh['reprove_command']}",
        "",
        "  Why DataHub is required: the notebook cannot see this leak (it happened",
        "  upstream in the warehouse), the feature store sees features but not their",
        "  ancestry, and model monitoring fires months later. Column-level lineage is",
        "  what makes the question answerable before release.",
        "",
        "-" * 25,
        f"LEAKED FEATURE   ablation {leaked['ablation_delta']:.2f}  -> {leaked['verdict']}",
        f"SAFE CONTROL     ablation {safe['ablation_delta']:.2f}  -> {safe['verdict']}",
        "",
        "The safe feature matters MORE by ablation, but Hindsight clears it.",
        "An ablation-only detector gets this exactly backwards.",
        "",
        "Independent point-in-time proof:",
        f"  AUC {point_in_time['observed_auc']:.6f} -> {point_in_time['point_in_time_auc']:.6f}",
        f"  verdict: {point_in_time['verdict']}",
        "",
        "Disclosure: The planted leak is total by construction; AUC 1.000000 is expected.",
        "Real-world leakage can be subtler.",
        "Policy: majority-loss (>50%) is configurable and is never sufficient without",
        "directional post-outcome lineage and a time violation.",
        "",
        "On the live path this verdict is written back to DataHub as:",
        *[f"  - {item}" for item in dh["live_path_writes_back"]],
        "each re-read to prove persistence. Publication is dry-run until approved.",
        "",
        f"DEMO STATUS: {report['status'].upper()}",
    ]
    return "\n".join(lines) + "\n"
