import re
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hindsight.web import create_app
from hindsight.web.glossary import GLOSSARY
from hindsight.web.health import datahub_health, reset_cache
from hindsight.web.runs import list_runs, record_run, runs_dir


@pytest.fixture
def client() -> TestClient:
    reset_cache()
    return TestClient(create_app(Path.cwd()))


@pytest.fixture
def clean_runs():
    """Keep real evidence out of the way while exercising empty/populated states."""
    directory = runs_dir(Path.cwd())
    backup = directory.with_name("runs.testbackup")
    if directory.exists():
        shutil.move(str(directory), str(backup))
    yield directory
    if directory.exists():
        shutil.rmtree(directory)
    if backup.exists():
        shutil.move(str(backup), str(directory))


# -- Shell ------------------------------------------------------------------


def test_every_page_renders_the_app_shell(client: TestClient) -> None:
    for path in ("/", "/audits", "/evidence", "/settings"):
        text = client.get(path).text
        assert 'class="sidebar"' in text, path
        assert 'href="/audits"' in text, path
        assert 'id="theme-toggle"' in text, path


def test_navigation_marks_the_current_page(client: TestClient) -> None:
    assert client.get("/audits").text.count("is-active") == 1
    assert client.get("/settings").text.count("is-active") == 1


# -- Honest connection state ------------------------------------------------


def test_status_is_probed_not_hardcoded(client: TestClient, monkeypatch) -> None:
    """The old console asserted 'connected' unconditionally. It must not."""
    monkeypatch.delenv("DATAHUB_GMS_URL", raising=False)
    reset_cache()
    text = client.get("/").text
    assert 'data-state="not_configured"' in text
    assert "DataHub evidence connected" not in text


def test_unreachable_datahub_reports_offline(monkeypatch) -> None:
    monkeypatch.setenv("DATAHUB_GMS_URL", "http://127.0.0.1:9")
    reset_cache()
    health = datahub_health(force=True)
    assert health["state"] == "offline"
    assert health["can_write"] is False


def test_health_api_exposes_state(client: TestClient) -> None:
    payload = client.get("/api/health/datahub").json()
    assert payload["state"] in {"connected", "degraded", "offline", "not_configured"}
    assert "can_write" in payload


def test_publish_controls_disabled_when_datahub_cannot_be_written(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.delenv("DATAHUB_GMS_URL", raising=False)
    reset_cache()
    text = client.post("/audits/run", follow_redirects=True).text
    assert "disabled" in text


# -- Runs -------------------------------------------------------------------


def test_audits_index_shows_an_empty_state_before_any_run(client: TestClient, clean_runs) -> None:
    text = client.get("/audits").text
    assert "No runs recorded yet" in text


def test_running_an_audit_records_history_and_redirects(client: TestClient, clean_runs) -> None:
    response = client.post("/audits/run", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/audits/")

    runs = list_runs(Path.cwd())
    assert len(runs) == 1
    assert runs[0]["release_decision"] == "block"

    listing = client.get("/audits").text
    assert runs[0]["run_id"] in listing
    assert "No runs recorded yet" not in listing


def test_unknown_run_returns_a_real_404_page(client: TestClient) -> None:
    response = client.get("/audits/does-not-exist")
    assert response.status_code == 404
    assert "That run does not exist" in response.text


def test_run_id_traversal_is_rejected(client: TestClient) -> None:
    assert client.get("/audits/..%2F..%2Fsecrets").status_code == 404


# -- Evidence detail --------------------------------------------------------


def test_audit_detail_renders_the_full_evidence(client: TestClient, clean_runs) -> None:
    run = record_run(Path.cwd(), client.get("/api/audit").json())
    text = client.get(f"/audits/{run['run_id']}").text
    # Plain-English layer: a newcomer must meet the conclusion before any jargon.
    assert "This model was cheating" in text
    assert "answer sheet" in text
    # ...and the exact evidence is still on the page for a reviewer.
    assert "1.000000" in text
    assert "0.833630" in text
    assert "0.21" in text and "0.24" in text
    assert "Importance gets this exactly backwards" in text
    assert 'id="activity-log"' in text
    assert "<noscript>" in text


def test_overview_explains_itself_to_a_newcomer(client: TestClient) -> None:
    text = client.get("/").text
    assert "What is this?" in text
    assert "target leakage" in text.lower()
    assert "Why this needs DataHub" in text


def test_every_info_control_resolves_to_a_glossary_entry(client: TestClient) -> None:
    for path in ("/", "/settings", "/evidence"):
        referenced = set(re.findall(r'data-info="([^"]+)"', client.get(path).text))
        missing = referenced - set(GLOSSARY)
        assert not missing, f"{path} references unknown glossary keys: {sorted(missing)}"


# -- APIs -------------------------------------------------------------------


def test_activity_api_reports_datahub_operations(client: TestClient) -> None:
    activity = client.get("/api/activity").json()["activity"]
    assert activity
    channels = {entry["channel"] for entry in activity}
    assert {"datahub", "mcp"} <= channels
    for entry in activity:
        assert entry["source"] in {"recorded", "computed", "live"}


def test_glossary_api_is_complete_and_plain_language(client: TestClient) -> None:
    glossary = client.get("/api/glossary").json()["glossary"]
    assert "target-leakage" in glossary
    for key, entry in glossary.items():
        assert entry["term"] and entry["short"], key
        assert len(entry["body"]) > 80, f"{key} needs a real explanation"


def test_audit_api_uses_deterministic_workflow(client: TestClient) -> None:
    report = client.get("/api/audit").json()
    assert report["release_decision"] == "block"
    assert report["verdict"] == "confirmed"
    assert report["validation"]["verdicts"]["safe_control"]["verdict"] == "clear_for_release"


def test_publish_is_dry_run_without_approval(client: TestClient, clean_runs) -> None:
    response = client.post(
        "/publish",
        data={
            "target_urn": "urn:li:dataset:dry-run",
            "server": "http://must-not-be-called.invalid",
        },
    )
    assert response.status_code == 200
    assert "awaiting human approval" in response.text.lower()


def test_health_endpoint(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
