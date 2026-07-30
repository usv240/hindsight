"""The DataHub integration, shown rather than listed.

"Use of DataHub" is the first judging criterion, and a checklist of surfaces
proves breadth while one real answer proves depth. The trace this renders is the
primitive the whole audit rests on, and it previously existed only in a markdown
file and a gitignored local report - so neither a clone nor the deployed image
had it, and the site never showed it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hindsight.web.app import create_app
from hindsight.web.artifacts import lineage_trace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRACE = PROJECT_ROOT / "evidence" / "integrations" / "lineage-trace.json"


@pytest.fixture(scope="module")
def page() -> str:
    return TestClient(create_app(PROJECT_ROOT)).get("/").text


def test_the_trace_is_committed_not_only_described() -> None:
    """A gitignored .local.json reaches neither a clone nor the image."""
    import subprocess

    tracked = subprocess.run(
        ["git", "ls-files", "evidence/integrations/lineage-trace.json"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    assert tracked, "the trace the landing page renders must be committed"


def test_the_trace_is_a_real_three_hop_answer() -> None:
    trace = lineage_trace(PROJECT_ROOT)
    assert trace is not None
    assert trace["available"] is True and trace["found"] is True
    assert len(trace["path"]) == 3
    assert trace["resolved_by"] == "agent_context_kit"


def test_the_middle_hop_is_a_datahub_query_entity() -> None:
    """This is the distinctive part: the catalog names the transformation."""
    trace = lineage_trace(PROJECT_ROOT)
    assert trace["path"][1].startswith("urn:li:query:")


def test_the_landing_page_shows_the_query_entity(page: str) -> None:
    assert "What the catalog actually answers" in page
    assert "DataHub query entity" in page
    assert "urn:li:query:" in page
    assert "Agent Context Kit" in page


def test_the_page_explains_why_two_flags_not_one(page: str) -> None:
    """An outage must never read as a clean bill of health, and the page says so."""
    assert "could not reach the catalog" in page
    assert "clean bill of health" in page


def test_every_used_surface_is_named_on_the_landing_page(page: str) -> None:
    for surface in ("Agent Context Kit", "MCP Server", "Context graph", "DataHub Actions"):
        assert surface in page, surface


def test_the_merged_contribution_is_visible(page: str) -> None:
    """The strongest bonus-criterion evidence should not require digging."""
    assert "datahub/pull/18705" in page
    assert "merged into" in page


def test_write_back_is_described_as_re_read(page: str) -> None:
    """Publishing is not the claim; publishing and reading it back is."""
    assert "read back" in page


def test_a_malformed_trace_hides_the_diagram_rather_than_crashing(tmp_path: Path) -> None:
    directory = tmp_path / "evidence" / "integrations"
    directory.mkdir(parents=True)
    target = directory / "lineage-trace.json"
    for junk in ("not json", "null", "[1,2,3]", '{"path": ["only", "two"]}'):
        target.write_text(junk, encoding="utf-8")
        assert lineage_trace(tmp_path) is None, junk


def test_the_rendered_path_matches_the_committed_record(page: str) -> None:
    """The page must not drift from the file it claims to be showing."""
    trace = json.loads(TRACE.read_text(encoding="utf-8"))
    assert trace["path"][0] in page
    assert trace["path"][2] in page
