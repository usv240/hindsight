from pathlib import Path

from hindsight.demo import render_judge_demo, run_judge_demo


def test_single_judge_demo_surfaces_ablation_reversal_and_both_proof_routes() -> None:
    report = run_judge_demo(Path.cwd())
    assert report["status"] == "passed"
    assert report["exit_code"] == 0
    assert report["deterministic_proof_fixture"]["verdict"] == "confirmed"
    assert report["safe_control"]["verdict"] == "clear_for_release"
    assert report["ablation_contrast"]["leaked_feature"] == 0.21
    assert report["ablation_contrast"]["safe_feature"] == 0.24
    assert report["point_in_time_proof_fixture"]["verdict"] == "confirmed"
    assert all(report["checks"].values())

    rendered = render_judge_demo(report)
    assert "ablation 0.21  -> confirmed" in rendered
    assert "ablation 0.24  -> clear_for_release" in rendered
    assert "exactly backwards" in rendered
    assert "total by construction" in rendered
