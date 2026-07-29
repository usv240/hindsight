"""The three DataHub surfaces beyond the MCP server: the Kit, Actions, the graph.

None of these may break the offline path. A judge with no DataHub, no network and
no optional extras must still get a working audit, so every integration degrades
to a stated reason rather than an exception.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hindsight.actions import HindsightReleaseGate
from hindsight.lineage import PathResolution, kit_available, resolve_column_path

# -- Agent Context Kit ------------------------------------------------------


def test_lineage_resolution_degrades_when_datahub_is_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("DATAHUB_GMS_URL", raising=False)
    monkeypatch.setattr(
        "hindsight.lineage.kit_available",
        lambda: (False, "DATAHUB_GMS_URL is not set"),
    )
    result = resolve_column_path(
        source_urn="urn:li:dataset:(p,a,PROD)",
        source_column="x",
        target_urn="urn:li:dataset:(p,b,PROD)",
        target_column="y",
    )
    assert result.available is False
    assert "DATAHUB_GMS_URL" in result.reason
    assert result.found is False


def test_kit_availability_reports_a_reason_rather_than_a_bare_false(monkeypatch) -> None:
    monkeypatch.delenv("DATAHUB_GMS_URL", raising=False)
    ok, reason = kit_available()
    assert ok is False
    assert reason, "an unavailable integration must say why"


def test_no_path_is_an_answer_not_a_failure() -> None:
    """The distinction that matters: 'the catalog says no path' is evidence
    against leakage. 'We could not ask' is not."""
    from hindsight.lineage import _is_no_path

    class ItemNotFoundError(Exception):
        pass

    assert _is_no_path(ItemNotFoundError("No lineage path found from A to B"))
    assert _is_no_path(RuntimeError("no lineage path found"))
    assert not _is_no_path(ConnectionError("connection refused"))
    assert not _is_no_path(TimeoutError())


def test_a_resolution_serialises_for_the_evidence_bundle() -> None:
    payload = PathResolution(available=True, found=True, hops=2, path=["a", "q", "b"]).to_dict()
    assert payload["resolved_by"] == "agent_context_kit"
    assert payload["hops"] == 2
    assert payload["path"] == ["a", "q", "b"]


# -- DataHub Actions --------------------------------------------------------


def test_the_action_imports_without_the_actions_framework() -> None:
    """Deployment-time dependency. The CLI must not require it."""
    assert HindsightReleaseGate is not None


@pytest.mark.parametrize(
    ("event", "expected_urn", "expected_type"),
    [
        (
            {"entityUrn": "urn:li:mlModel:(p,m,PROD)", "entityType": "mlModel"},
            "urn:li:mlModel:(p,m,PROD)",
            "mlModel",
        ),
        ({"urn": "urn:li:dataset:(p,d,PROD)"}, "urn:li:dataset:(p,d,PROD)", "dataset"),
        ({}, None, None),
        ({"entityUrn": None}, None, None),
    ],
)
def test_event_parsing(event: dict, expected_urn: str | None, expected_type: str | None) -> None:
    urn, entity_type = HindsightReleaseGate._extract(event)
    assert urn == expected_urn
    assert entity_type == expected_type


def test_the_action_ignores_entity_types_it_does_not_watch() -> None:
    action = HindsightReleaseGate.create(
        {"project_root": str(Path.cwd()), "entity_types": ["mlModel"], "raise_incident": False},
        None,
    )
    action.act({"entityUrn": "urn:li:dashboard:(p,d)", "entityType": "dashboard"})
    assert action.audited == [], "a dashboard must not trigger a model release audit"


def test_the_action_audits_a_watched_entity_and_records_the_verdict() -> None:
    action = HindsightReleaseGate.create(
        {"project_root": str(Path.cwd()), "raise_incident": False},
        None,
    )
    action.act({"entityUrn": "urn:li:mlModel:(p,credit,PROD)", "entityType": "mlModel"})

    assert len(action.audited) == 1
    result = action.audited[0]
    assert result["release_decision"] == "block"
    assert result["verdict"] == "confirmed"
    assert result["incident_raised"] is False, "notification was disabled for this run"


def test_a_failing_audit_never_takes_the_pipeline_down() -> None:
    """An Action that raises stops every downstream consumer of the event stream."""
    action = HindsightReleaseGate.create(
        {"project_root": "/nonexistent", "raise_incident": False}, None
    )
    action.act({"entityUrn": "urn:li:mlModel:(p,m,PROD)", "entityType": "mlModel"})
    assert action.audited == []


def test_the_action_never_publishes_on_its_own() -> None:
    """It may notify. Only a person may write the evidence record.

    Checked at the source level: an autonomous publish would be a silent
    mutation of governed metadata, which is the thing this project argues
    against, so the guarantee is worth pinning rather than trusting.
    """
    source = Path("src/hindsight/actions/release_gate.py").read_text(encoding="utf-8")
    assert "publish_audit" not in source
    assert "approve_writeback" not in source


def test_the_pipeline_config_filters_before_the_action_runs() -> None:
    config = Path("docker/hindsight-action.yml").read_text(encoding="utf-8")
    assert "EntityChangeEvent_v1" in config
    assert 'operation: "CREATE"' in config
    assert 'entityType: "mlModel"' in config
    assert "hindsight.actions.release_gate:HindsightReleaseGate" in config
