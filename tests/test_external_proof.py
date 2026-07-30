"""The recorded numbers on the evidence page must still be true.

The console renders a committed artifact rather than retraining a model when a
stranger loads the page. That is the right call for a public demo and it creates
one risk: the page can keep showing a result the code no longer produces.

So these tests re-run the real audit and the real sweep, and compare. If
behaviour changes, this fails - rather than the website quietly lying.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hindsight.sweep import sweep
from hindsight.validation.point_in_time import run_credit_validation

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = PROJECT_ROOT / "examples" / "adapter"
PROOF = PROJECT_ROOT / "evidence" / "adapter" / "external-data-proof.json"


@pytest.fixture(scope="module")
def recorded() -> dict:
    assert PROOF.is_file(), "run scripts/record_external_proof.py"
    return json.loads(PROOF.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def fresh() -> dict:
    return run_credit_validation(EXAMPLE / "scenario.json")


def test_the_recorded_audit_still_matches_a_fresh_run(recorded: dict, fresh: dict) -> None:
    case = fresh["leakage_case"]
    result = recorded["result"]

    assert result["status"] == fresh["status"]
    assert result["baseline_auc"] == pytest.approx(case["baseline_auc"], abs=5e-5)
    assert result["observed_auc"] == pytest.approx(case["observed_auc"], abs=5e-5)
    assert result["point_in_time_auc"] == pytest.approx(case["point_in_time_auc"], abs=5e-5)
    assert result["advantage_retained_pct"] == pytest.approx(
        case["advantage_retained"] * 100, abs=5e-3
    )
    assert result["collapsed"] == case["collapsed"]
    assert (
        result["excluded_post_cutoff_records"]
        == fresh["reconstruction"]["excluded_post_cutoff_records"]
    )


def test_the_recorded_sweep_still_matches_a_fresh_run(recorded: dict) -> None:
    live = sweep(EXAMPLE / "scenario_wide.json")
    assert recorded["sweep"]["flagged"] == live["flagged"]

    live_by_name = {item["feature"]: item for item in live["findings"]}
    for item in recorded["sweep"]["findings"]:
        actual = live_by_name[item["feature"]]
        assert item["advantage_lost"] == pytest.approx(actual["advantage_lost"], abs=5e-5)
        assert item["collapsed"] == actual["collapsed"]


def test_the_recorded_file_list_matches_what_is_on_disk(recorded: dict) -> None:
    """A judge downloads these, so a missing one is a broken promise.

    Compared by line count, not byte count. These are text files and git
    normalises their line endings on checkout, so a size recorded on Windows
    does not match the same file in a clean clone - which is exactly how this
    assertion failed in CI while passing locally.
    """
    for entry in recorded["dataset"]["files"]:
        path = EXAMPLE / entry["name"]
        assert path.is_file(), entry["name"]
        lines = len(path.read_text(encoding="utf-8").splitlines())
        assert lines == entry["lines"], entry["name"]


def test_the_commands_shown_are_real_commands(recorded: dict) -> None:
    from hindsight.cli import build_parser

    known = set(build_parser()._subparsers._group_actions[0].choices)  # noqa: SLF001
    for command in recorded["commands"]:
        # "uv run hindsight <subcommand> ..." - the subcommand is the 4th token.
        parts = command.split()
        assert parts[:3] == ["uv", "run", "hindsight"], command
        assert parts[3] in known, command


def test_the_page_still_discloses_that_a_ranking_is_not_a_verdict(recorded: dict) -> None:
    text = recorded["sweep"]["how_to_read_this"].lower()
    assert "triage" in text and "not a verdict" in text


# --- The page and the downloads --------------------------------------------


def _client():
    from fastapi.testclient import TestClient

    from hindsight.web.app import create_app

    return TestClient(create_app(PROJECT_ROOT))


def test_the_evidence_page_shows_the_external_result(recorded: dict) -> None:
    body = _client().get("/evidence").text
    assert "Does it work on data we did not create" in body
    assert str(recorded["result"]["observed_auc"]) in body
    assert str(recorded["result"]["point_in_time_auc"]) in body
    # The trap row must be visible, not just the flagged one.
    assert "support_tickets_snapshot" in body


def test_every_advertised_file_downloads(recorded: dict) -> None:
    client = _client()
    for entry in recorded["dataset"]["files"]:
        response = client.get(f"/examples/adapter/{entry['name']}")
        assert response.status_code == 200, entry["name"]
        assert entry["name"] in response.headers["content-disposition"]
        served = len(response.text.splitlines())
        assert served == entry["lines"], entry["name"]


def test_the_download_route_serves_only_the_allowlist() -> None:
    """It is public on the hosted demo, so it must not be a file server."""
    client = _client()
    for hostile in (
        "../../pyproject.toml",
        "..%2F..%2Fpyproject.toml",
        "scenario.json.bak",
        ".env",
    ):
        assert client.get(f"/examples/adapter/{hostile}").status_code in (400, 404), hostile
