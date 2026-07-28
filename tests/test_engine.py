from datetime import UTC, datetime

import pytest

from hindsight.engine import audit_case
from hindsight.models import AuditCase, Verdict

BASE = {
    "case_id": "case",
    "model_urn": "urn:model",
    "feature_urn": "urn:feature",
    "lineage_path": ("source.field", "feature.field"),
    "source_kind": "post_outcome",
    "source_available_at": datetime(2026, 1, 2, tzinfo=UTC),
    "prediction_time": datetime(2026, 1, 1, tzinfo=UTC),
}


@pytest.mark.parametrize("proof,pit", [(True, False), (False, True), (True, True)])
def test_confirmed_requires_valid_confirmation_route(proof: bool, pit: bool) -> None:
    result = audit_case(
        AuditCase(**BASE, deterministic_cutoff_proof=proof, point_in_time_advantage_collapsed=pit)
    )
    assert result.verdict is Verdict.CONFIRMED
    assert result.exit_code == 3


def test_direction_and_time_without_confirmation_is_high_confidence() -> None:
    assert audit_case(AuditCase(**BASE)).verdict is Verdict.HIGH_CONFIDENCE


def test_large_ablation_delta_cannot_confirm_leakage() -> None:
    safe = dict(BASE)
    safe.update(
        source_kind="pre_outcome",
        source_available_at=datetime(2025, 12, 31, tzinfo=UTC),
        ablation_delta=0.99,
    )
    result = audit_case(AuditCase(**safe))
    assert result.verdict is Verdict.CLEAR_FOR_RELEASE
    assert result.exit_code == 0


def test_missing_lineage_produces_insufficient_metadata() -> None:
    incomplete = dict(BASE)
    incomplete["lineage_path"] = ()
    result = audit_case(AuditCase(**incomplete))
    assert result.verdict is Verdict.INSUFFICIENT_METADATA
    assert result.exit_code == 2


def test_common_ancestry_without_direction_needs_review() -> None:
    case = dict(BASE)
    case.update(
        source_kind="pre_outcome",
        source_available_at=datetime(2025, 12, 31, tzinfo=UTC),
        suspicious_common_ancestry=True,
    )
    assert audit_case(AuditCase(**case)).verdict is Verdict.NEEDS_REVIEW


# -- Confirmation routes ----------------------------------------------------


def test_deterministic_sql_proof_confirms_without_a_statistical_collapse() -> None:
    """The second confirmation route Codex adjudicated in round 2.

    A transformation that joins a post-outcome source with no availability guard
    proves post-cutoff data entered the feature. Requiring the point-in-time
    collapse *as well* would let a case escape purely because a threshold landed
    on the wrong side of it.
    """
    from hindsight.workflow import _resolve_verdict

    verdict, route = _resolve_verdict("high_confidence", deterministic_proof=True)
    assert verdict == "confirmed"
    assert route == "deterministic_sql_time_proof"


def test_point_in_time_collapse_is_reported_as_its_own_route() -> None:
    from hindsight.workflow import _resolve_verdict

    verdict, route = _resolve_verdict("confirmed", deterministic_proof=False)
    assert verdict == "confirmed"
    assert route == "point_in_time_collapse"


def test_no_route_promotes_a_case_that_never_established_direction() -> None:
    """Neither route may rescue weak evidence."""
    from hindsight.workflow import _resolve_verdict

    for weak in ("needs_review", "insufficient_metadata", "clear_for_release"):
        verdict, route = _resolve_verdict(weak, deterministic_proof=True)
        assert verdict == weak, weak
        assert route == "none", weak
