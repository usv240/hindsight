from pathlib import Path

from hindsight.workflow import run_demo_audit


def test_demo_audit_blocks_release_and_stops_before_writeback() -> None:
    report = run_demo_audit(
        scenario_path=Path("scenarios/credit_default/scenario.json"),
        transformation_path=Path("examples/leaky_feature.sql"),
        remediation_path=Path("examples/remediation.sql"),
        post_outcome_table="payment_events_after_decision",
    )

    assert report["release_decision"] == "block"
    assert report["verdict"] == "confirmed"
    assert report["exit_code"] == 3
    assert all(report["checks"].values())
    assert report["remediation"]["verification"]["status"] == "safe"
    assert report["writeback"]["mutation_performed"] is False
    assert report["writeback"]["status"] == "awaiting_human_approval"
