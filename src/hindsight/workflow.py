from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from hindsight.detectors import verify_temporal_cutoff
from hindsight.validation import run_credit_validation


def run_demo_audit(
    *,
    scenario_path: Path,
    transformation_path: Path,
    remediation_path: Path,
    post_outcome_table: str,
) -> dict[str, Any]:
    """Produce a deterministic evidence bundle without performing a mutation."""
    transformation = transformation_path.read_text(encoding="utf-8")
    sql_verification = verify_temporal_cutoff(
        transformation,
        post_outcome_table=post_outcome_table,
    )
    validation = run_credit_validation(scenario_path)
    leakage_verdict = validation["verdicts"]["leakage_case"]
    safe_verdict = validation["verdicts"]["safe_control"]
    should_block = (
        sql_verification.status == "violation"
        and validation["status"] == "passed"
        and leakage_verdict["verdict"] == "confirmed"
        and safe_verdict["verdict"] == "clear_for_release"
    )
    remediation = remediation_path.read_text(encoding="utf-8")
    remediation_verification = verify_temporal_cutoff(
        remediation,
        post_outcome_table=post_outcome_table,
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
        "verdict": leakage_verdict["verdict"],
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
                "status": leakage_verdict["verdict"],
                "reason": leakage_verdict["reasons"][0],
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
