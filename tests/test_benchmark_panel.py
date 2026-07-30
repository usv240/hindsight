"""The benchmark was the project's strongest measurement and was invisible on the site.

It lived in the README and a JSON file, so anyone who watched the video and clicked
the demo never saw it. These tests cover the shaping and the rendering, and
especially the two properties that make the chart honest rather than flattering.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hindsight.web.app import create_app
from hindsight.web.benchmark import load

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def bench() -> dict:
    data = load(PROJECT_ROOT)
    assert data is not None, "evaluations/benchmark.json should be committed"
    return data


@pytest.fixture(scope="module")
def page() -> str:
    return TestClient(create_app(PROJECT_ROOT)).get("/evidence").text


def test_every_band_is_fully_accounted_for(bench: dict) -> None:
    """The bars are part-to-whole. If the parts do not sum, the chart lies."""
    for row in bench["rows"]:
        assert row["statistical"] + row["deterministic_only"] + row["missed"] == row["cases"]
        assert row["statistical_pct"] + row["deterministic_only_pct"] == 100


def test_nothing_was_missed(bench: dict) -> None:
    assert all(row["missed"] == 0 for row in bench["rows"])
    assert bench["false_negatives"] == 0
    assert bench["false_positives"] == 0


def test_the_statistical_route_decays_and_the_data_says_where(bench: dict) -> None:
    """The caption is derived, so it cannot drift from the measurement."""
    fired = [row["reach_pct"] for row in bench["rows"] if row["statistical_fired"]]
    blind = [row["reach_pct"] for row in bench["rows"] if not row["statistical_fired"]]
    assert fired and blind, "the sweep should cross the threshold"
    # Every band where it fired has more reach than every band where it did not.
    assert min(fired) > max(blind)
    assert bench["blind_from_pct"] == max(blind)


def test_the_auc_delta_shrinks_monotonically(bench: dict) -> None:
    deltas = [row["auc_delta"] for row in bench["rows"]]
    assert deltas == sorted(deltas, reverse=True)
    assert deltas[-1] < 0.01, "the faintest band should be near-invisible"


def test_the_chart_renders_on_the_evidence_page(page: str) -> None:
    assert "What happens as the defect gets subtler" in page
    assert "bench-plot" in page
    assert page.count("bench-band") >= 7


def test_identity_is_never_colour_alone(page: str) -> None:
    """A legend for two series, plus a table repeating every value."""
    assert "Caught by retraining and comparing" in page
    assert "Caught only by reading the code" in page
    assert "Table view of every band" in page
    # Screen readers get the split without seeing the fills.
    assert "caught by statistics" in page


def test_the_page_keeps_the_tautology_disclosure(page: str) -> None:
    """A near-perfect score that is partly true by construction must say so here.

    Not only in a file nobody opens. This is the disclosure that makes the rest
    of the number believable.
    """
    assert "Read the perfect score with care" in page
    assert "by construction" in page


def test_the_series_colours_are_not_the_status_colours() -> None:
    """These are two methods, not two states.

    Reusing green and red would say "good route / bad route", which is false: the
    deterministic route is not better, it is differently blind.
    """
    css = (PROJECT_ROOT / "src/hindsight/web/static/styles.css").read_text(encoding="utf-8")
    block = css[css.index("--series-statistical") :][:400]
    for status in ("--ok", "--danger", "--warn"):
        assert status not in block, f"{status} must not be reused as a series colour"


def test_a_missing_benchmark_file_hides_the_section_rather_than_crashing(
    tmp_path: Path,
) -> None:
    assert load(tmp_path) is None


def test_a_corrupt_benchmark_file_is_ignored(tmp_path: Path) -> None:
    directory = tmp_path / "evaluations"
    directory.mkdir()
    for junk in ("not json at all", "null", "[1, 2, 3]", '{"by_coverage": []}'):
        (directory / "benchmark.json").write_text(junk, encoding="utf-8")
        assert load(tmp_path) is None, junk


def test_the_committed_numbers_match_the_shaping(bench: dict) -> None:
    raw = json.loads((PROJECT_ROOT / "evaluations" / "benchmark.json").read_text(encoding="utf-8"))
    assert bench["cases"] == sum(band["cases"] for band in raw["by_coverage"])
    assert bench["false_positives"] == raw["counts"]["false_positive"]
