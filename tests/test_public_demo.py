"""The hosted demo must not be able to do the things the local tool can.

Two routes cost real resources: running an audit trains a model, and publishing
mutates a DataHub catalog. On a public URL neither is acceptable, so these tests
assert the refusal happens and that the pages still work without them.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hindsight.web import demo_mode
from hindsight.web.app import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def public_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv(demo_mode.ENV_VAR, "1")
    return TestClient(create_app(PROJECT_ROOT))


@pytest.fixture
def local_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.delenv(demo_mode.ENV_VAR, raising=False)
    return TestClient(create_app(PROJECT_ROOT))


def _csrf(client: TestClient) -> str:
    return client.app.state.csrf_token


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_enabled_accepts_the_usual_spellings(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv(demo_mode.ENV_VAR, value)
    assert demo_mode.enabled() is True


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "  "])
def test_disabled_by_default_and_by_falsey_values(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(demo_mode.ENV_VAR, value)
    assert demo_mode.enabled() is False


def test_running_an_audit_is_refused(public_client: TestClient) -> None:
    response = public_client.post("/audits/run", data={"csrf_token": _csrf(public_client)})
    assert response.status_code == 403
    assert "read-only demo" in response.json()["detail"]


def test_publishing_is_refused(public_client: TestClient) -> None:
    response = public_client.post(
        "/publish",
        data={
            "csrf_token": _csrf(public_client),
            "target_urn": "urn:li:dataset:(urn:li:dataPlatform:duckdb,x,PROD)",
            "approve_writeback": "true",
        },
    )
    assert response.status_code == 403


def test_refusal_precedes_csrf_so_no_work_happens_first(
    public_client: TestClient,
) -> None:
    """A wrong CSRF token must still 403, not 400.

    The order matters: if CSRF were checked first, a caller with a valid token
    would reach the audit. The refusal has to be the outermost gate.
    """
    response = public_client.post("/audits/run", data={"csrf_token": "wrong"})
    assert response.status_code == 403


def test_every_page_still_renders(public_client: TestClient) -> None:
    for route in ("/", "/audits", "/evidence", "/settings"):
        assert public_client.get(route).status_code == 200


def test_scenario_cards_link_to_recorded_runs_instead_of_posting(
    public_client: TestClient,
) -> None:
    body = public_client.get("/").text
    assert 'action="/audits/run"' not in body
    assert 'class="scenario-card" href="/audits/' in body


def test_write_back_form_is_replaced_by_an_explanation(
    public_client: TestClient,
) -> None:
    latest = public_client.get("/audits/latest", follow_redirects=True)
    assert latest.status_code == 200
    assert 'action="/publish"' not in latest.text
    assert "Write-back is disabled on the public demo" in latest.text


def test_the_local_tool_keeps_both_affordances(local_client: TestClient) -> None:
    """The guard must be opt-in, or it silently breaks the real product."""
    assert 'action="/audits/run"' in local_client.get("/").text
    latest = local_client.get("/audits/latest", follow_redirects=True)
    assert 'action="/publish"' in latest.text


def test_seeded_runs_are_committed_so_a_fresh_clone_is_not_empty() -> None:
    """A clone with no runs opens on an empty console and hosts nothing.

    This asserts against git rather than the filesystem, because the local
    directory is full of untracked runs that a judge will never receive.
    """
    import subprocess

    tracked = subprocess.run(
        ["git", "ls-files", "evidence/runs/*.json"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split()
    assert len(tracked) >= 5, f"expected seeded runs to be committed, found {tracked}"


def test_scenario_links_keeps_only_the_newest_run_per_scenario() -> None:
    runs = [
        {"scenario": "a", "run_id": "3"},
        {"scenario": "b", "run_id": "2"},
        {"scenario": "a", "run_id": "1"},
        {"run_id": "no-scenario"},
        {"scenario": "c"},
    ]
    assert demo_mode.scenario_links(runs) == {"a": "3", "b": "2"}
