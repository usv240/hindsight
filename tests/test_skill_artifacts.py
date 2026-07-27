from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).parents[1]
SKILL = ROOT / "skills" / "datahub-ml-release-audit"


def _validator() -> ModuleType:
    path = SKILL / "scripts" / "validate_evidence.py"
    spec = importlib.util.spec_from_file_location("validate_evidence", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_skill_has_upstream_shape_and_safety_contract() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\nname: datahub-ml-release-audit\n")
    assert "Plain ablation" not in text  # wording may vary; rule must remain explicit below
    assert "ablation can prioritize investigation but cannot prove leakage" in text
    assert "explicit user approval of the exact write plan" in text
    assert "references/verdict-contract.md" in text


def test_confirmed_requires_real_confirmation_route() -> None:
    validate = _validator().validate
    bundle = {
        "verdict": "confirmed",
        "model_urn": "urn:li:mlModel:credit_default_v4",
        "prediction_time": "2026-07-27T12:00:00Z",
        "directional_outcome_lineage": True,
        "availability_violation": True,
        "deterministic_cutoff_proof": False,
        "point_in_time": {"performed": False},
        "safe_control": {"performed": True, "remained_safe": True},
    }
    assert "confirmed requires deterministic proof or policy-qualified PIT collapse" in validate(
        bundle
    )


def test_valid_confirmed_and_clear_bundles() -> None:
    validate = _validator().validate
    confirmed = {
        "verdict": "confirmed",
        "model_urn": "urn:li:mlModel:credit_default_v4",
        "prediction_time": "2026-07-27T12:00:00Z",
        "directional_outcome_lineage": True,
        "availability_violation": True,
        "deterministic_cutoff_proof": True,
        "point_in_time": {"performed": False},
        "safe_control": {"performed": True, "remained_safe": True},
    }
    clear = {
        "verdict": "clear_for_release",
        "model_urn": "urn:li:mlModel:credit_default_v4",
        "prediction_time": "2026-07-27T12:00:00Z",
        "directional_outcome_lineage": False,
        "availability_violation": False,
        "deterministic_cutoff_proof": False,
        "point_in_time": {"performed": False},
        "safe_control": {"performed": True, "remained_safe": True},
    }
    assert validate(confirmed) == []
    assert validate(clear) == []
