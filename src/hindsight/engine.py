from __future__ import annotations

from hindsight.models import AuditCase, AuditResult, Verdict

OUTCOME_SOURCE_KINDS = frozenset({"label", "post_outcome"})


def audit_case(case: AuditCase) -> AuditResult:
    """Apply the deterministic Hindsight verdict lattice to one feature path."""
    missing = _missing_evidence(case)
    evidence = {
        "lineage_path": list(case.lineage_path),
        "source_kind": case.source_kind,
        "source_available_at": _iso(case.source_available_at),
        "prediction_time": _iso(case.prediction_time),
        "deterministic_cutoff_proof": case.deterministic_cutoff_proof,
        "point_in_time_advantage_collapsed": case.point_in_time_advantage_collapsed,
        "ablation_delta": case.ablation_delta,
    }

    if missing:
        return AuditResult(
            case_id=case.case_id,
            verdict=Verdict.INSUFFICIENT_METADATA,
            reasons=("Required evidence is missing: " + ", ".join(missing),),
            evidence=evidence,
        )

    directional = case.source_kind in OUTCOME_SOURCE_KINDS
    late = case.source_available_at > case.prediction_time  # type: ignore[operator]

    if directional and late:
        if case.deterministic_cutoff_proof:
            return AuditResult(
                case.case_id,
                Verdict.CONFIRMED,
                ("A deterministic time proof shows post-cutoff outcome data entered the feature.",),
                evidence,
            )
        if case.point_in_time_advantage_collapsed:
            return AuditResult(
                case.case_id,
                Verdict.CONFIRMED,
                ("The feature advantage collapsed under point-in-time reconstruction.",),
                evidence,
            )
        return AuditResult(
            case.case_id,
            Verdict.HIGH_CONFIDENCE,
            ("Directional outcome lineage and an availability-time violation are established.",),
            evidence,
        )

    if case.suspicious_common_ancestry:
        return AuditResult(
            case.case_id,
            Verdict.NEEDS_REVIEW,
            ("Common ancestry is suspicious, but directional post-outcome flow is not proven.",),
            evidence,
        )

    return AuditResult(
        case.case_id,
        Verdict.CLEAR_FOR_RELEASE,
        ("No directional post-outcome availability violation was established.",),
        evidence,
    )


def _missing_evidence(case: AuditCase) -> list[str]:
    missing: list[str] = []
    if not case.metadata_complete:
        missing.append("metadata_complete")
    if not case.lineage_path:
        missing.append("lineage_path")
    if case.source_kind is None:
        missing.append("source_kind")
    if case.source_available_at is None:
        missing.append("source_available_at")
    if case.prediction_time is None:
        missing.append("prediction_time")
    return missing


def _iso(value: object) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None
