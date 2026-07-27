from pathlib import Path

from fastapi.testclient import TestClient

from hindsight.web import create_app
from hindsight.web.glossary import GLOSSARY


def _client() -> TestClient:
    return TestClient(create_app(Path.cwd()))


def test_console_renders_real_evidence() -> None:
    response = _client().get("/")
    assert response.status_code == 200
    assert "Your model is not smarter" in response.text
    assert "1.000000" in response.text
    assert "0.833630" in response.text
    assert "0.924842" in response.text
    assert "0.21" in response.text
    assert "0.24" in response.text
    assert "Importance gets this exactly backwards" in response.text
    assert "total by construction" in response.text
    assert "payment.available_at &lt;= application.prediction_time" in response.text


def test_console_explains_itself_to_a_newcomer() -> None:
    """A visitor who has never seen this project must be able to follow it."""
    text = _client().get("/").text
    assert "What is this?" in text
    assert "target leakage" in text.lower()
    # The originality argument must be on the page, not only in the README.
    assert "Why this needs DataHub" in text
    assert "column-level lineage" in text


def test_console_exposes_theme_toggle_and_both_themes() -> None:
    text = _client().get("/").text
    assert 'id="theme-toggle"' in text
    assert "hindsight-theme" in text  # pre-paint theme restore, avoids a flash


def test_console_shows_backend_activity_log() -> None:
    text = _client().get("/").text
    assert 'id="activity-log"' in text
    assert "Backend activity" in text
    # Static fallback for visitors without JavaScript.
    assert "<noscript>" in text


def test_every_info_control_resolves_to_a_glossary_entry() -> None:
    """No info button may point at a term that does not exist."""
    import re

    text = _client().get("/").text
    referenced = set(re.findall(r'data-info="([^"]+)"', text))
    assert referenced, "expected the console to expose info controls"
    missing = referenced - set(GLOSSARY)
    assert not missing, f"info controls without glossary entries: {sorted(missing)}"


def test_activity_api_reports_datahub_operations() -> None:
    response = _client().get("/api/activity")
    assert response.status_code == 200
    activity = response.json()["activity"]
    assert activity, "expected a non-empty activity feed"
    channels = {entry["channel"] for entry in activity}
    assert "datahub" in channels
    assert "mcp" in channels
    for entry in activity:
        assert entry["source"] in {"recorded", "computed", "live"}


def test_glossary_api_is_complete_and_plain_language() -> None:
    glossary = _client().get("/api/glossary").json()["glossary"]
    assert "target-leakage" in glossary
    for key, entry in glossary.items():
        assert entry["term"], key
        assert entry["short"], key
        assert len(entry["body"]) > 80, f"{key} needs a real explanation"


def test_audit_api_uses_deterministic_workflow() -> None:
    response = _client().get("/api/audit")
    assert response.status_code == 200
    report = response.json()
    assert report["release_decision"] == "block"
    assert report["verdict"] == "confirmed"
    assert report["validation"]["verdicts"]["safe_control"]["verdict"] == "clear_for_release"


def test_console_publish_form_is_dry_run_without_checkbox() -> None:
    response = _client().post(
        "/publish",
        data={
            "target_urn": "urn:li:dataset:dry-run",
            "server": "http://must-not-be-called.invalid",
        },
    )
    assert response.status_code == 200
    assert "awaiting human approval" in response.text.lower()


def test_health_endpoint() -> None:
    assert _client().get("/health").json() == {"status": "ok"}
