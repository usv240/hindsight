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


def test_a_collapsed_safe_control_cannot_confirm_via_point_in_time() -> None:
    """A reconstruction that also collapses a legitimate feature proves nothing.

    This bundle claims the suspect feature collapsed under point-in-time
    reconstruction, and in the same breath reports that the known-good control
    collapsed too. That means the reconstruction is producing false positives, so
    the collapse is not evidence. The validator accepted it as consistent, which
    is a false positive wearing a confirmation - the exact failure this project
    exists to prevent.
    """
    validate = _validator().validate
    bundle = {
        "verdict": "confirmed",
        "model_urn": "urn:li:mlModel:credit_default_v4",
        "prediction_time": "2026-07-27T12:00:00Z",
        "directional_outcome_lineage": True,
        "availability_violation": True,
        "deterministic_cutoff_proof": False,
        "point_in_time": {
            "performed": True,
            "advantage_retained": 0.01,
            "collapse_threshold": 0.05,
        },
        "safe_control": {"performed": True, "remained_safe": False},
    }
    assert (
        "PIT collapse cannot confirm without a predictive pre-cutoff control that remained safe"
        in validate(bundle)
    )

    # The deterministic route does not depend on the reconstruction, so it still stands.
    assert validate({**bundle, "deterministic_cutoff_proof": True}) == []
