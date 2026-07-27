import pytest

from hindsight.writeback import publish_audit


def _bundle() -> dict:  # type: ignore[type-arg]
    return {
        "case_id": "case",
        "release_decision": "block",
        "verdict": "confirmed",
        "writeback": {"planned_types": ["field_tag", "audit_document"]},
    }


def test_writeback_is_a_no_network_dry_run_without_approval() -> None:
    report = publish_audit(
        _bundle(),
        target_urn="urn:li:dataset:test",
        server="http://must-not-be-called.invalid",
    )
    assert report["status"] == "awaiting_human_approval"
    assert report["mutation_performed"] is False


def test_approved_publisher_rejects_non_blocking_bundle_before_network() -> None:
    bundle = _bundle()
    bundle["release_decision"] = "review"
    with pytest.raises(ValueError, match="confirmed/block"):
        publish_audit(
            bundle,
            target_urn="urn:li:dataset:test",
            server="http://must-not-be-called.invalid",
            approved=True,
        )
