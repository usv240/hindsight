from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import hindsight.web.health as health_module
from hindsight.config import AuditConfig
from hindsight.validation import run_credit_validation
from hindsight.web.app import _fingerprint, create_app
from hindsight.web.runs import get_run, list_runs, record_run
from hindsight.web.timeline import build_timeline
from hindsight.workflow import run_demo_audit
from hindsight.writeback.datahub import _validate_destination


@pytest.mark.parametrize(
    ("scenario_path", "case_id", "leak_source", "safe_feature"),
    [
        (
            "scenarios/credit_default/scenario.json",
            "credit-default-leaked-payment-event",
            "payment_events_after_decision.payment_recorded_at",
            "prior_delinquencies",
        ),
        (
            "scenarios/fraud_screening/scenario.json",
            "fraud-screening-post-authorisation-dispute",
            "disputes_after_authorisation.dispute_filed_at",
            "account_age_days",
        ),
        (
            "scenarios/hospital_readmission/scenario.json",
            "readmission-post-discharge-followup",
            "followup_appointments_after_discharge.booked_at",
            "prior_admissions_12m",
        ),
    ],
)
def test_every_domain_emits_its_own_evidence(
    scenario_path: str,
    case_id: str,
    leak_source: str,
    safe_feature: str,
) -> None:
    report = run_credit_validation(Path(scenario_path))
    leakage = report["verdicts"]["leakage_case"]
    context = report["evidence_context"]

    assert leakage["case_id"] == case_id
    assert leakage["evidence"]["lineage_path"][0] == leak_source
    assert context["safe_feature_name"] == safe_feature

    scenario = json.loads(Path(scenario_path).read_text(encoding="utf-8"))
    timeline = build_timeline({"validation": report}, scenario)
    rendered_nodes = {(track.label, track.column) for track in timeline.tracks}
    expected_asset, expected_column = leak_source.rsplit(".", 1)
    assert (expected_asset, expected_column) not in rendered_nodes
    leak_target = context["leakage_lineage_path"][-1].rsplit(".", 1)
    assert tuple(leak_target) in rendered_nodes


def test_fraud_page_never_relabels_credit_evidence_as_fraud() -> None:
    client = TestClient(create_app(Path.cwd()))
    response = client.post(
        "/audits/run",
        data={
            "csrf_token": client.app.state.csrf_token,
            "scenario": "fraud_screening",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "fraud-screening-post-authorisation-dispute" in response.text
    assert "disputes_after_authorisation" in response.text
    assert "account_age_days" in response.text
    assert "payment_events_after_decision" not in response.text
    assert "Supporting evidence" in response.text


def test_state_changing_forms_require_csrf_token() -> None:
    client = TestClient(create_app(Path.cwd()))
    assert client.post("/audits/run").status_code == 403
    assert (
        client.post(
            "/publish",
            data={"target_urn": "urn:li:dataset:test"},
        ).status_code
        == 403
    )


def test_unknown_web_scenario_is_rejected_instead_of_silently_running_credit() -> None:
    client = TestClient(create_app(Path.cwd()))
    response = client.post(
        "/audits/run",
        data={
            "csrf_token": client.app.state.csrf_token,
            "scenario": "not-a-real-domain",
        },
    )
    assert response.status_code == 400


def test_cache_fingerprint_includes_columns_binding_and_config_file() -> None:
    config = AuditConfig.load(Path("audits/credit_default.json"), Path.cwd())
    baseline = _fingerprint(config)
    assert _fingerprint(replace(config, available_column="recorded_at")) != baseline
    assert _fingerprint(replace(config, prediction_column="decision_at")) != baseline
    assert _fingerprint(replace(config, target_urn="urn:li:dataset:bound")) != baseline


def test_health_cache_is_scoped_to_the_requested_server(monkeypatch) -> None:
    calls: list[str | None] = []

    def fake_probe(target: str | None):  # type: ignore[no-untyped-def]
        calls.append(target)
        return {"state": "connected", "server": target}

    monkeypatch.setattr(health_module, "_probe", fake_probe)
    health_module.reset_cache()
    health_module.datahub_health("http://one")
    health_module.datahub_health("http://two")
    assert calls == ["http://one", "http://two"]


def test_custom_time_column_names_reach_both_sql_checks(tmp_path: Path) -> None:
    leaky = tmp_path / "leaky.sql"
    safe = tmp_path / "safe.sql"
    leaky.write_text(
        "SELECT * FROM src JOIN events_after_decision evt ON src.id = evt.id",
        encoding="utf-8",
    )
    safe.write_text(
        "SELECT * FROM src JOIN events_after_decision evt "
        "ON src.id = evt.id AND evt.recorded_at <= src.decision_at",
        encoding="utf-8",
    )
    report = run_demo_audit(
        scenario_path=Path("scenarios/credit_default/scenario.json"),
        transformation_path=leaky,
        remediation_path=safe,
        post_outcome_table="events_after_decision",
        available_column="recorded_at",
        prediction_column="decision_at",
    )
    assert report["sql_verification"]["available_column"] == "recorded_at"
    assert report["remediation"]["verification"]["status"] == "safe"


def test_writeback_destination_rejects_wrong_binding_and_credentialed_url() -> None:
    bundle = {"audit_config": {"target_urn": "urn:li:dataset:expected"}}
    with pytest.raises(ValueError, match="bound to"):
        _validate_destination(
            bundle,
            target_urn="urn:li:dataset:other",
            server="https://datahub.example",
        )
    with pytest.raises(ValueError, match="credentials"):
        _validate_destination(
            {"audit_config": {"target_urn": "urn:li:dataset:expected"}},
            target_urn="urn:li:dataset:expected",
            server="https://user:secret@datahub.example",
        )


def test_writeback_destination_rejects_unbound_evidence() -> None:
    with pytest.raises(ValueError, match="bound to an exact target"):
        _validate_destination(
            {"audit_config": {"target_urn": None}},
            target_urn="urn:li:dataset:requested",
            server="https://datahub.example",
        )


def test_run_history_preserves_an_immutable_evidence_snapshot(tmp_path: Path) -> None:
    bundle = {
        "audit_config": {"name": "snapshot", "target_urn": None},
        "case_id": "snapshot-case",
        "verdict": "confirmed",
        "release_decision": "block",
        "exit_code": 3,
        "validation": {"runtime_seconds": 0.1, "rows": 10},
    }
    run = record_run(tmp_path, bundle, scenario="credit_default")
    stored = get_run(tmp_path, run["run_id"])
    assert stored is not None
    assert stored["schema_version"] == 2
    assert stored["evidence_bundle"] == bundle
    assert len(stored["evidence_sha256"]) == 64

    summaries = list_runs(tmp_path)
    assert "evidence_bundle" not in summaries[0]
    assert summaries[0]["evidence_sha256"] == stored["evidence_sha256"]


def test_deterministic_confirmation_always_blocks_even_when_pit_policy_does_not_fire() -> None:
    config = AuditConfig.load(Path("audits/fraud_screening.json"), Path.cwd())
    report = run_demo_audit(
        scenario_path=config.scenario_path,
        transformation_path=config.transformation_path,
        remediation_path=config.remediation_path,
        post_outcome_table=config.post_outcome_table,
        available_column=config.available_column,
        prediction_column=config.prediction_column,
    )
    assert report["confirmation_route"] == "deterministic_sql_time_proof"
    assert report["validation"]["leakage_case"]["collapsed"] is False
    assert report["verdict"] == "confirmed"
    assert report["release_decision"] == "block"
    assert report["exit_code"] == 3
