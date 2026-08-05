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

import re
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


# --- The demo script --------------------------------------------------------
#
# The video is the only unmet judging criterion, and a script that names a beat
# the console no longer has wastes a take. The previous script went stale without
# anyone noticing: it predated the sweep, the external dataset, the benchmark
# chart and the lineage trace, so following it would have produced a video that
# missed the strongest material.


def _script() -> str:
    return (PROJECT_ROOT / "docs" / "DEMO_SCRIPT.md").read_text(encoding="utf-8")


def _flat(text: str) -> str:
    """Collapse whitespace so prose rewrapping cannot break an assertion.

    A previous version asserted the literal "availability timestamp". The script
    still said it, wrapped across two lines, and the test failed on formatting
    rather than on meaning.
    """
    return " ".join(text.split()).lower()


def test_every_quoted_screen_phrase_exists_somewhere_in_the_console() -> None:
    """The real invariant: never tell the presenter to point at something absent.

    Derived from the script rather than a fixed list, so rewriting the running
    order stays free while pointing at a removed section still fails.
    """
    script = _script()
    client = TestClient(create_app(PROJECT_ROOT))
    console = " ".join(
        [
            client.get("/").text,
            client.get("/evidence").text,
            client.get("/audits/latest", follow_redirects=True).text,
        ]
    )

    # Only the stage directions point at the screen. Quoted text anywhere else is
    # something the presenter says, and a spoken line has no business existing in
    # the console. An earlier version scanned the whole file and failed on the cut
    # list, which quotes a line of narration.
    directions = [line for line in script.splitlines() if line.startswith("**On screen:**")]
    assert directions, "the script must tell the presenter what is on screen"

    cues = {cue for line in directions for cue in re.findall(r'"([^"]{12,60})"', line)}
    for cue in cues:
        assert _flat(cue) in _flat(console), f"script points at something the console lacks: {cue}"
    assert len(cues) >= 3, "expected the script to name several on-screen sections"


def test_the_script_maps_its_beats_to_the_judging_criteria() -> None:
    """Three minutes is less than the material, so the cut has to be deliberate."""
    script = _flat(_script())
    for criterion in ("use of datahub", "originality", "technical execution", "real-world"):
        assert criterion in script, criterion
    assert "run long" in script, "the script must say what to cut first"


def test_the_script_still_forbids_the_claims_the_readme_disclaims() -> None:
    script = _flat(_script())
    assert "do not say" in script
    assert "availability timestamp" in script
    assert "visibility public" in script
