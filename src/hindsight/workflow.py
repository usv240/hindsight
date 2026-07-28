from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from hindsight.detectors import verify_temporal_cutoff
from hindsight.models import BLOCKING_VERDICTS, Verdict
from hindsight.validation import run_credit_validation


def run_demo_audit(
    *,
    scenario_path: Path,
    transformation_path: Path,
    remediation_path: Path,
    post_outcome_table: str,
    available_column: str = "available_at",
    prediction_column: str = "prediction_time",
) -> dict[str, Any]:
    """Produce a deterministic evidence bundle without performing a mutation."""
    transformation = transformation_path.read_text(encoding="utf-8")
    sql_verification = verify_temporal_cutoff(
        transformation,
        post_outcome_table=post_outcome_table,
        available_column=available_column,
        prediction_column=prediction_column,
    )
    validation = run_credit_validation(scenario_path)
    leakage_verdict = validation["verdicts"]["leakage_case"]
    safe_verdict = validation["verdicts"]["safe_control"]

    # Two independent routes reach `confirmed`, and the audit takes whichever
    # fires. The point-in-time route lives in the validation above. The second -
    # a deterministic SQL/time proof - was specified but never wired: a
    # transformation that joins a post-outcome table with no availability guard
    # proves post-cutoff information entered the feature, with no retraining and
    # no dependence on where a statistical threshold happens to sit.
    deterministic_proof = sql_verification.status == "violation"
    verdict, confirmation_route = _resolve_verdict(
        leakage_verdict["verdict"], deterministic_proof=deterministic_proof
    )

    # The release action must be a pure function of the calibrated verdict.
    # Requiring an unrelated safe-control or reconstruction check here can
    # produce an incoherent confirmed/review state, even though deterministic
    # proof is independently sufficient.
    should_block = verdict in {v.value for v in BLOCKING_VERDICTS}
    remediation = remediation_path.read_text(encoding="utf-8")
    remediation_verification = verify_temporal_cutoff(
        remediation,
        post_outcome_table=post_outcome_table,
        available_column=available_column,
        prediction_column=prediction_column,
    )
    checks = {
        "transformation_violation_proven": sql_verification.status == "violation",
        "point_in_time_confirmation_passed": validation["status"] == "passed",
        "safe_control_cleared": safe_verdict["verdict"] == "clear_for_release",
        "proposed_remediation_verifies_safe": remediation_verification.status == "safe",
        "no_catalog_mutation_without_approval": True,
    }
    return {
        "schema_version": 1,
        "case_id": leakage_verdict["case_id"],
        "release_decision": "block" if should_block else "review",
        "verdict": verdict,
        "confirmation_route": confirmation_route,
        "point_in_time_verdict": leakage_verdict["verdict"],
        "checks": checks,
        "trace": [
            {
                "step": "transformation_verification",
                "status": sql_verification.status,
                "reason": sql_verification.reason,
            },
            {
                "step": "point_in_time_reconstruction",
                "status": validation["status"],
                "excluded_post_cutoff_records": validation["reconstruction"][
                    "excluded_post_cutoff_records"
                ],
            },
            {
                "step": "deterministic_verdict",
                "status": verdict,
                "reason": _route_reason(confirmation_route, leakage_verdict["reasons"][0]),
            },
            {
                "step": "safe_control",
                "status": safe_verdict["verdict"],
                "ablation_delta": validation["safe_control"]["observed_advantage"],
            },
            {
                "step": "writeback",
                "status": "awaiting_human_approval",
            },
        ],
        "sql_verification": sql_verification.to_dict(),
        "validation": validation,
        "remediation": {
            "path": f"examples/{remediation_path.name}",
            "sha256": hashlib.sha256(remediation.encode()).hexdigest(),
            "verification": remediation_verification.to_dict(),
        },
        "writeback": {
            "status": "awaiting_human_approval",
            "planned_types": [
                "field_tag",
                "structured_property",
                "audit_document",
                "active_incident",
            ],
            "mutation_performed": False,
        },
        "exit_code": 3 if should_block else 2,
    }


def _resolve_verdict(point_in_time_verdict: str, *, deterministic_proof: bool) -> tuple[str, str]:
    """Take the strongest verdict any single route can justify.

    A deterministic SQL/time proof confirms on its own: if the transformation
    joins a post-outcome table with no availability guard, post-cutoff data
    demonstrably entered the feature. Requiring a statistical collapse *as well*
    would let a feature escape on the wrong side of a threshold despite proof.
    Neither route can promote a case that never established directional flow -
    `insufficient_metadata` and `needs_review` are left untouched.
    """
    if point_in_time_verdict == Verdict.CONFIRMED.value:
        return point_in_time_verdict, "point_in_time_collapse"
    if deterministic_proof and point_in_time_verdict == Verdict.HIGH_CONFIDENCE.value:
        return Verdict.CONFIRMED.value, "deterministic_sql_time_proof"
    return point_in_time_verdict, "none"


def _route_reason(route: str, fallback: str) -> str:
    if route == "deterministic_sql_time_proof":
        return (
            "The transformation joins a post-outcome source with no availability cutoff, "
            "which proves post-cutoff information entered the feature."
        )
    return fallback
