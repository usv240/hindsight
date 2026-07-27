import json
from pathlib import Path

import pytest

from hindsight.cli import _is_loopback, main
from hindsight.config import AuditConfig, AuditConfigError


def test_default_audit_config_loads_the_seeded_scenario() -> None:
    config = AuditConfig.default(Path.cwd())
    assert config.name == "credit_default"
    assert config.scenario_path.exists()
    assert config.transformation_path.exists()
    assert config.post_outcome_table == "payment_events_after_decision"


def test_audit_config_round_trips_from_disk() -> None:
    config = AuditConfig.load(Path("audits/credit_default.json"), Path.cwd())
    assert config.name == "credit_default"
    assert config.scenario_path.exists()
    assert config.to_dict()["post_outcome_table"] == "payment_events_after_decision"


def test_missing_audit_config_is_reported_clearly(tmp_path: Path) -> None:
    with pytest.raises(AuditConfigError, match="not found"):
        AuditConfig.load(tmp_path / "nope.json", tmp_path)


def test_audit_config_rejects_missing_required_keys(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text(json.dumps({"name": "broken"}), encoding="utf-8")
    with pytest.raises(AuditConfigError, match="missing required keys"):
        AuditConfig.load(path, tmp_path)


def test_audit_config_rejects_paths_that_do_not_exist(tmp_path: Path) -> None:
    path = tmp_path / "ghost.json"
    path.write_text(
        json.dumps(
            {
                "scenario": "nowhere/scenario.json",
                "transformation_sql": "nowhere/a.sql",
                "remediation_sql": "nowhere/b.sql",
                "post_outcome_table": "events",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(AuditConfigError, match="does not exist"):
        AuditConfig.load(path, tmp_path)


def test_describes_is_permissive_only_when_no_target_is_declared() -> None:
    unbound = AuditConfig.default(Path.cwd())
    assert unbound.describes("urn:li:dataset:anything")

    from dataclasses import replace

    bound = replace(unbound, target_urn="urn:li:dataset:the-real-one")
    assert bound.describes("urn:li:dataset:the-real-one")
    assert not bound.describes("urn:li:dataset:something-else")


def test_publish_refuses_to_tag_an_asset_the_audit_does_not_describe(tmp_path: Path) -> None:
    """The evidence must be about the asset it is written to."""
    config_path = tmp_path / "bound.json"
    root = Path.cwd()
    config_path.write_text(
        json.dumps(
            {
                "name": "bound",
                "scenario": str(root / "scenarios/credit_default/scenario.json"),
                "transformation_sql": str(root / "examples/leaky_feature.sql"),
                "remediation_sql": str(root / "examples/remediation.sql"),
                "post_outcome_table": "payment_events_after_decision",
                "target_urn": "urn:li:dataset:the-audited-one",
            }
        ),
        encoding="utf-8",
    )
    exit_code = main(
        [
            "publish-audit",
            "--audit",
            str(config_path),
            "--target-urn",
            "urn:li:dataset:a-completely-different-asset",
            "--server",
            "http://must-not-be-called.invalid",
            "--output",
            str(tmp_path / "out.json"),
        ]
    )
    assert exit_code == 2, "publishing to an undescribed asset must fail closed"


def test_loopback_detection() -> None:
    assert _is_loopback("127.0.0.1")
    assert _is_loopback("localhost")
    assert _is_loopback("::1")
    assert not _is_loopback("0.0.0.0")
    assert not _is_loopback("10.0.0.5")
