"""The README is the judge's entry point, so its claims are load-bearing.

Every number here was correct when written and drifted anyway, because nothing
checked. These tests pin the claims a reader can verify in sixty seconds: the
commands exist, the sample output matches what the commands actually print, and
the exit codes are what the text says they are.

Two real defects this would have caught:

* "Exit 3 means leakage confirmed" sat directly under `hindsight demo`, which
  exits 0 because it is a self-check. A judge running `echo $?` saw 0.
* The Level 3 blocks showed a tidy summary table while both commands printed
  131 lines of raw JSON. The numbers were right; the experience was not.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
README = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "hindsight.cli", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=900,
    )


# --- Commands ---------------------------------------------------------------


def test_every_command_in_the_reference_table_exists() -> None:
    """A README command that argparse rejects is worse than an undocumented one."""
    from hindsight.cli import build_parser

    documented = set(re.findall(r"\| `hindsight ([a-z-]+)", README))
    assert documented, "the reference table should not be empty"

    parser = build_parser()
    real = {
        choice
        for action in parser._actions  # noqa: SLF001
        if getattr(action, "choices", None)
        for choice in action.choices
    }
    assert documented <= real, f"README documents commands that do not exist: {documented - real}"


# --- Exit codes -------------------------------------------------------------


def test_demo_is_a_self_check_and_exits_zero() -> None:
    """The README used to promise exit 3 here. It exits 0, and says so now."""
    assert _run("demo").returncode == 0
    assert "`demo` is a self-check and exits `0`" in README


def test_the_gate_commands_carry_the_verdict_in_the_exit_code() -> None:
    assert _run("demo-audit").returncode == 3
    assert (
        _run("sweep-features", "--scenario", "examples/adapter/scenario_wide.json").returncode == 3
    )


# --- Sample output ----------------------------------------------------------


@pytest.mark.parametrize(
    ("args", "lines"),
    [
        (
            ("validate-point-in-time", "--scenario", "examples/adapter/scenario.json"),
            [
                "baseline, honest features only   0.825 AUC",
                "with the suspect feature         0.993",
                "rebuilt as of the decision       0.826",
                "post-cutoff records excluded     664",
                "VERDICT: confirmed",
            ],
        ),
        (
            ("sweep-features", "--scenario", "examples/adapter/scenario_wide.json"),
            [
                "plan_changes_to_date           0.9932   0.8257    0.1674  True",
                "support_tickets_snapshot       0.9601   0.9601    0.0000  False",
                "FLAGGED (1): plan_changes_to_date",
            ],
        ),
    ],
    ids=["point-in-time", "sweep"],
)
def test_the_readme_shows_what_the_command_actually_prints(
    args: tuple[str, ...], lines: list[str]
) -> None:
    stdout = _run(*args).stdout
    for line in lines:
        assert line in stdout, f"command no longer prints: {line!r}"
        assert line in README, f"README no longer shows: {line!r}"


def test_the_machine_readable_form_is_still_available() -> None:
    """Making stdout human-readable must not remove the JSON contract."""
    result = _run("sweep-features", "--scenario", "examples/adapter/scenario_wide.json", "--json")
    payload = json.loads(result.stdout)
    assert payload["candidates"] == 5
    assert payload["flagged"] == ["plan_changes_to_date"]


# --- Claims that cite a file ------------------------------------------------


def test_every_relative_link_resolves() -> None:
    """A broken link in the judge's entry point is a bad first impression."""
    targets = set(re.findall(r"\]\((?!https?://)([^)#]+)", README))
    missing = sorted(t for t in targets if not (PROJECT_ROOT / t).exists())
    assert not missing, f"README links to missing paths: {missing}"


def test_the_benchmark_table_matches_the_measured_file() -> None:
    data = json.loads((PROJECT_ROOT / "evaluations" / "benchmark.json").read_text(encoding="utf-8"))
    assert data["cases"] == 42
    assert "42 cases, 0 false positives, 0 false negatives" in README

    counts = data["counts"]
    assert counts["false_positive"] == 0
    assert counts["false_negative"] == 0

    for row in data["by_coverage"]:
        coverage = int(round(float(row["coverage"]) * 100))
        if coverage in {100, 70, 40, 15, 2}:
            assert f"{row['mean_auc_delta']:.4f}" in README, coverage


def test_the_contributions_table_lists_every_upstream_pr() -> None:
    """This table went stale the moment a third PR was raised."""
    for pr in ("18705", "18822", "68"):
        assert pr in README, f"upstream PR {pr} is missing from the contributions table"
