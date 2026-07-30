"""The impact section argues the project matters. It must not overclaim doing it.

The whole page's credibility rests on not overstating, so a section written to
impress is the easiest place to lose it. These tests pin the two properties that
keep it honest: every headline number is either cited or labelled as ours, and
the section names who this does *not* serve.

An earlier draft claimed "0 of those studies looked upstream of the notebook".
One of the two is a literature survey, so asserting what it did not examine was
not defensible. It was replaced with a figure from our own benchmark.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hindsight.web.app import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def page() -> str:
    return TestClient(create_app(PROJECT_ROOT)).get("/").text


def test_the_section_is_on_the_landing_page(page: str) -> None:
    assert "How often does this actually happen" in page


def test_every_prevalence_figure_carries_its_source(page: str) -> None:
    """A number without a citation is an assertion."""
    assert "294" in page and "Kapoor" in page and "Patterns" in page
    assert "100k+" in page and "K&auml;stner" in page or "Kästner" in page
    assert "ASE" in page


def test_our_own_measurement_is_labelled_as_ours(page: str) -> None:
    """Not dressed up as third-party evidence."""
    assert "false positives across 21 legitimate queries" in page
    assert "our own benchmark" in page


def test_it_says_who_this_does_not_serve(page: str) -> None:
    """Naming the non-fit is what makes the fit believable."""
    assert "Not built for" in page
    assert "Recommendation and ranking" in page
    assert "no per-row decision moment" in page


def test_the_prerequisites_are_stated_rather_than_glossed(page: str) -> None:
    assert "What you need to use it on your own work" in page
    # The honest ceiling: the full story needs fine-grained lineage, not just DataHub.
    assert "column-level" in page
    assert "connectors emit fine-grained lineage" in page


def test_the_zero_setup_path_is_offered(page: str) -> None:
    """The one tier that genuinely works for anyone should be reachable from here."""
    assert "scan-sql" in page
    assert "no DataHub, no config" in page


def test_unparseable_files_are_never_called_clean_on_the_page(page: str) -> None:
    """The page must repeat the guarantee, not just the capability."""
    assert "unchecked" in page
    assert "never as clean" in page


def test_it_does_not_claim_what_a_survey_did_not_examine(page: str) -> None:
    """Guards the specific overreach that was removed."""
    assert "of those studies looked upstream" not in page


# --- Prior art --------------------------------------------------------------
#
# "Does this already exist?" is the first question an originality judgement asks.
# Answering it with citations, and conceding where existing tools are the better
# answer, is more convincing than claiming novelty.


@pytest.fixture(scope="module")
def evidence_page() -> str:
    return TestClient(create_app(PROJECT_ROOT)).get("/evidence").text


def test_prior_art_is_named_with_citations(evidence_page: str) -> None:
    assert "Does this already exist?" in evidence_page
    for work in ("2209.03345", "2503.14723", "2603.10742"):
        assert work in evidence_page, work


def test_it_concedes_where_feature_stores_are_the_better_answer(evidence_page: str) -> None:
    """A tool that cannot name its own alternative is not credible."""
    assert "Feast" in evidence_page
    assert "prevents it" in evidence_page
    assert "better answer than detecting it" in evidence_page


def test_the_gap_is_stated_precisely_not_vaguely(evidence_page: str) -> None:
    """The claim is about a taxonomy, not about being generally superior."""
    assert "Overlap, Multi-test" in evidence_page
    assert "notebook-internal" in evidence_page
    assert "manual feature derivation before split" in evidence_page
