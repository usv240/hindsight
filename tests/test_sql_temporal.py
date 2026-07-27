from pathlib import Path

from hindsight.detectors.sql_temporal import verify_temporal_cutoff


def _verify(name: str):  # type: ignore[no-untyped-def]
    sql = Path(f"examples/{name}").read_text(encoding="utf-8")
    return verify_temporal_cutoff(
        sql,
        post_outcome_table="payment_events_after_decision",
    )


def test_leaky_transformation_is_blocked() -> None:
    result = _verify("leaky_feature.sql")
    assert result.status == "violation"
    assert result.exit_code == 3
    assert "payment_events_after_decision" in result.referenced_tables


def test_point_in_time_remediation_is_cleared() -> None:
    result = _verify("remediation.sql")
    assert result.status == "safe"
    assert result.exit_code == 0
    assert result.cutoff_predicates


def test_unparseable_sql_is_indeterminate_not_safe() -> None:
    result = verify_temporal_cutoff(
        "SELECT FROM WHERE",
        post_outcome_table="payment_events_after_decision",
    )
    assert result.status == "indeterminate"
    assert result.exit_code == 2


def test_irrelevant_query_is_clear() -> None:
    result = verify_temporal_cutoff(
        "SELECT application_id FROM applications_at_decision_time",
        post_outcome_table="payment_events_after_decision",
    )
    assert result.status == "safe"


def test_cutoff_on_an_unrelated_table_does_not_clear_post_outcome_source() -> None:
    result = verify_temporal_cutoff(
        """
        SELECT * FROM payment_events_after_decision AS payment
        JOIN applications_at_decision_time AS application USING (customer_id)
        JOIN ingestion_log AS log USING (customer_id)
        WHERE log.available_at <= application.prediction_time
        """,
        post_outcome_table="payment_events_after_decision",
    )
    assert result.status == "violation"
