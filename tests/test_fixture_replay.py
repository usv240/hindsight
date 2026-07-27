import shutil
from pathlib import Path

from hindsight.fixtures import run_fixture_replay

FIXTURE = Path("fixtures/credit_default")


def test_fixture_replay_is_offline_fast_and_matches_ground_truth() -> None:
    report = run_fixture_replay(FIXTURE)
    assert report["status"] == "passed"
    assert report["exit_code"] == 0
    assert report["external_services_used"] == []
    assert report["runtime_seconds"] < 60
    assert report["release_decision"] == "block"
    assert report["verdicts"]["leakage_case"]["verdict"] == "confirmed"
    assert report["verdicts"]["safe_control"]["verdict"] == "clear_for_release"
    assert all(report["checks"].values())


def test_fixture_tampering_fails_closed(tmp_path: Path) -> None:
    copied = tmp_path / "fixture"
    shutil.copytree(FIXTURE, copied)
    lineage = copied / "responses/lineage.json"
    lineage.write_text(lineage.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    report = run_fixture_replay(copied)
    assert report["status"] == "integrity_failed"
    assert report["exit_code"] == 2
    assert any("sha256 mismatch" in error for error in report["errors"])
