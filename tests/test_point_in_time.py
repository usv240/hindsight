from pathlib import Path
from typing import Any

import pytest

from hindsight.validation.point_in_time import run_credit_validation

SCENARIO = Path("scenarios/credit_default/scenario.json")


@pytest.fixture(scope="module")
def report() -> dict[str, Any]:
    return run_credit_validation(SCENARIO)


def test_point_in_time_reconstruction_distinguishes_leak_from_safe_signal(
    report: dict[str, Any],
) -> None:
    assert report["status"] == "passed"
    assert report["reconstruction"]["excluded_post_cutoff_records"] == 4000
    assert report["leakage_case"]["collapsed"] is True
    assert report["safe_control"]["collapsed"] is False
    assert report["safe_control"]["observed_advantage"] >= 0.05
    assert report["verdicts"]["leakage_case"]["verdict"] == "confirmed"
    assert report["verdicts"]["safe_control"]["verdict"] == "clear_for_release"


def test_frozen_scenario_is_deterministic_except_for_runtime(
    report: dict[str, Any],
) -> None:
    first = report.copy()
    second = run_credit_validation(SCENARIO)
    first.pop("runtime_seconds")
    second.pop("runtime_seconds")
    assert first == second
