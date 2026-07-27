from pathlib import Path

from fastapi.testclient import TestClient

from hindsight.web import create_app


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
    assert "awaiting_human_approval" not in response.text


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
    assert "Awaiting Human Approval" in response.text
    assert "Mutation performed: false" in response.text


def test_health_endpoint() -> None:
    assert _client().get("/health").json() == {"status": "ok"}
