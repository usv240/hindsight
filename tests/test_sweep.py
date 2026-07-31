"""Ranking many features, without turning a ranking into a verdict.

Every other entry point asks "is this feature leaking?", which assumes you
already suspect one. This asks "which of these is wrong", which is the question
someone with a forty-feature model actually has.

The property that matters most here is the negative one: a feature can be highly
predictive and completely legitimate, and the sweep must not flag it. That is the
same trap the single-feature audit demonstrates, and it is easier to fail at
scale, because the obvious way to rank a list of features is by importance.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hindsight.sweep import SweepConfigError, sweep

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WIDE = PROJECT_ROOT / "examples" / "adapter" / "scenario_wide.json"


@pytest.fixture(scope="module")
def report() -> dict:
    return sweep(WIDE)


def _by_name(report: dict) -> dict[str, dict]:
    return {item["feature"]: item for item in report["findings"]}


def test_the_wide_example_is_committed() -> None:
    assert WIDE.is_file()
    assert (WIDE.parent / "feature_snapshots.csv").is_file()


def test_every_candidate_is_evaluated(report: dict) -> None:
    findings = _by_name(report)
    assert report["candidates"] == len(findings)
    assert all(item["status"] == "evaluated" for item in findings.values())


def test_only_the_leaking_feature_is_flagged(report: dict) -> None:
    assert report["flagged"] == ["plan_changes_to_date"]


def test_a_strong_but_legitimate_feature_is_not_flagged(report: dict) -> None:
    """The whole point. This feature is more predictive than the baseline and clean.

    An importance-ranked detector would put it near the top. Ranking by advantage
    lost to the cutoff puts it at zero, which is correct.
    """
    honest = _by_name(report)["support_tickets_snapshot"]
    assert honest["observed_auc"] > 0.90, "should be genuinely predictive"
    assert honest["advantage_lost"] == pytest.approx(0.0, abs=1e-6)
    assert honest["collapsed"] is False
    assert honest["feature"] not in report["flagged"]


def test_the_leak_loses_far_more_than_anything_else(report: dict) -> None:
    findings = _by_name(report)
    leak = findings["plan_changes_to_date"]["advantage_lost"]
    others = [
        item["advantage_lost"] for name, item in findings.items() if name != "plan_changes_to_date"
    ]
    assert leak > 0.10
    assert leak > max(others) * 10


def test_findings_are_ordered_by_advantage_lost(report: dict) -> None:
    losses = [
        item["advantage_lost"] for item in report["findings"] if item["status"] == "evaluated"
    ]
    assert losses == sorted(losses, reverse=True)


def test_it_says_a_ranking_is_not_a_verdict(report: dict) -> None:
    """The disclosure is load-bearing: triage must not read as proof."""
    text = report["how_to_read_this"].lower()
    assert "triage" in text
    assert "not a verdict" in text
    assert report["ranked_by"] == "advantage_lost"


def test_long_form_scenarios_are_refused_with_a_reason() -> None:
    """Sweeping needs a wide table; saying so beats guessing at columns."""
    with pytest.raises(SweepConfigError, match="wide_snapshots"):
        sweep(PROJECT_ROOT / "examples" / "adapter" / "scenario.json")


def test_a_bad_column_does_not_abandon_the_sweep(tmp_path: Path) -> None:
    """One unusable column must not hide the findings for all the others."""
    config = json.loads(WIDE.read_text(encoding="utf-8"))
    adapter = config["point_in_time_adapter"]
    adapter["sweep_features"] = ["plan_changes_to_date", "column_that_does_not_exist"]
    for key in ("applications", "feature_snapshots"):
        adapter[key]["path"] = str(WIDE.parent / adapter[key]["path"])

    path = tmp_path / "partly_broken.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    result = sweep(path)
    statuses = {item["feature"]: item["status"] for item in result["findings"]}
    assert statuses["plan_changes_to_date"] == "evaluated"
    assert statuses["column_that_does_not_exist"] == "could_not_evaluate"
    assert result["flagged"] == ["plan_changes_to_date"]


def test_the_safe_control_is_not_audited_against_itself() -> None:
    """It is the comparison baseline, so sweeping it would be meaningless."""
    config = json.loads(WIDE.read_text(encoding="utf-8"))
    safe = config["point_in_time_adapter"]["columns"]["safe_feature"]
    assert safe not in [item["feature"] for item in sweep(WIDE)["findings"]]


def test_no_scratch_files_are_left_behind() -> None:
    sweep(WIDE)
    assert not list(WIDE.parent.glob(".sweep-*")), "temporary variants must be cleaned up"


# --- Exit codes are the CI contract -----------------------------------------


def _cli(*args: str) -> int:
    import subprocess
    import sys

    return subprocess.run(
        [sys.executable, "-m", "hindsight.cli", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    ).returncode


def test_an_invalid_config_does_not_report_success() -> None:
    """A misconfigured sweep exiting 0 is a false negative wearing a pass.

    That is the exact failure this project exists to prevent, and it was in our
    own CLI: sweeping a long-form scenario printed "invalid_input" and returned
    0, so a pipeline would go green having audited nothing.
    """
    assert _cli("sweep-features", "--scenario", "examples/adapter/scenario.json") == 2


def test_a_flagged_feature_blocks_the_pipeline() -> None:
    assert _cli("sweep-features", "--scenario", "examples/adapter/scenario_wide.json") == 3


def test_the_readme_documents_a_real_verify_sql_invocation() -> None:
    """The README told judges to pass --sql, which argparse rejects."""
    from hindsight.cli import build_parser

    verify = build_parser()._subparsers._group_actions[0].choices["verify-sql"]  # noqa: SLF001
    flags = {option for action in verify._actions for option in action.option_strings}  # noqa: SLF001
    assert "--sql" not in flags, "if this flag is added, update the README row too"

    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    assert "verify-sql --sql" not in readme
