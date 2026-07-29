"""The identity panel answers "a verdict about what, exactly".

Its failure mode is not a crash, it is confidently naming the wrong artifact.
A page that shows the leaky model's URN above a clean verdict, or calls a
legitimate pre-cutoff fact a defect, is worse than one that says nothing.

The first version read fixtures/<slug>/ground_truth.json and fell back to
fixtures/credit_default when a scenario had none. Only credit_default has one,
so every scenario rendered the credit model: a fraud audit claimed to examine
days_since_last_payment on credit_default_v1_leaky. The tests passed throughout,
because they only ever exercised credit_default. Hence _live() below, which
drives every scenario the way the app does.
"""

from __future__ import annotations

import glob
import json
from pathlib import Path

from hindsight.web.subject import describe

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = (
    "credit_default",
    "credit_default_subtle",
    "credit_default_fixed",
    "fraud_screening",
    "hospital_readmission",
)


def _live(slug: str) -> dict:
    """Describe a scenario from its real config and a committed run."""
    from hindsight.web.app import _audit_config

    config = _audit_config(PROJECT_ROOT, slug)
    scenario = json.loads(Path(config.scenario_path).read_text(encoding="utf-8"))
    for path in sorted(glob.glob(str(PROJECT_ROOT / "evidence/runs/*.json")), reverse=True):
        run = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(run, dict) or (run.get("scenario") or run.get("audit")) != slug:
            continue
        return describe(
            PROJECT_ROOT,
            Path(config.scenario_path).parent.name,
            bundle=run.get("evidence_bundle") or {},
            run=run,
            subject=config.subject,
            scenario_cutoff=scenario.get("prediction_time", ""),
        )
    raise AssertionError(f"no committed run for {slug}; the seeded runs should cover it")


def test_every_scenario_names_its_own_model_and_feature() -> None:
    expected = {
        "credit_default": ("credit_default_v1_leaky", "days_since_last_payment"),
        "credit_default_subtle": ("credit_default_v1_leaky", "days_since_last_payment"),
        "credit_default_fixed": ("credit_default_v2_safe", "prior_delinquencies"),
        "fraud_screening": ("fraud_screening_v1_leaky", "disputes_on_account"),
        "hospital_readmission": ("readmission_v1_leaky", "followup_appointments_booked"),
    }
    for slug, (model, feature) in expected.items():
        described = _live(slug)
        assert described["model"]["name"] == model, slug
        assert described["feature"]["name"] == feature, slug


def test_no_two_scenario_families_share_a_model() -> None:
    """The bug was every scenario showing one model. Assert they are distinct."""
    models = {
        slug: _live(slug)["model"]["name"]
        for slug in ("credit_default", "fraud_screening", "hospital_readmission")
    }
    assert len(set(models.values())) == 3, models


def test_the_safe_control_is_a_different_model_to_the_leaky_one() -> None:
    """Showing the leaky model above an ALLOW verdict would be a lie."""
    assert (
        _live("credit_default")["model"]["name"] != _live("credit_default_fixed")["model"]["name"]
    )


def test_every_scenario_reports_its_own_reach() -> None:
    """9, 22 and 31 days are different defects; one number for all would be a tell."""
    gaps = {
        slug: _live(slug)["timing"]["gap_days"]
        for slug in ("credit_default", "fraud_screening", "hospital_readmission")
    }
    assert len(set(gaps.values())) == 3, gaps
    assert all(value > 0 for value in gaps.values()), gaps


def test_a_pre_cutoff_fact_is_not_described_as_a_violation() -> None:
    """The identical row means the opposite thing either side of the cutoff."""
    late = _live("credit_default")["timing"]
    fine = _live("credit_default_fixed")["timing"]

    assert late["late"] is True
    assert "too late" in late["gap_label"]

    assert fine["late"] is False
    assert "too late" not in fine["gap_label"]
    assert "already knowable" in fine["summary"].lower()


def test_urns_are_the_ones_the_audit_actually_used() -> None:
    """Display must not drift from the evidence the lineage was resolved against."""
    truth = json.loads(
        (PROJECT_ROOT / "fixtures/credit_default/ground_truth.json").read_text(encoding="utf-8")
    )
    described = _live("credit_default")
    assert described["model_urn"] == truth["model_urn"]
    assert described["feature_urn"] == truth["feature_urn"]


def test_feature_names_the_table_it_lives_in() -> None:
    assert _live("credit_default")["feature"]["table"] == "feature_pipeline_leaky"
    assert _live("fraud_screening")["feature"]["table"] == "fraud_feature_pipeline"


def test_a_scenario_without_a_fixture_still_gets_its_timing() -> None:
    """Dates come from the scenario definition and bundle, not only the fixture."""
    timing = _live("fraud_screening")["timing"]
    assert timing["cutoff"] and timing["available"]
    assert timing["gap_days"] == 9


def test_synthetic_data_is_disclosed_beside_realistic_looking_urns() -> None:
    assert _live("credit_default")["synthetic"] is True


def test_missing_run_drops_bookkeeping_rather_than_inventing_it() -> None:
    described = describe(PROJECT_ROOT, "credit_default", bundle={}, run=None, subject="leaked")
    assert described["meta"] == []
    # Identity still resolves from the fixture; only run-scoped rows disappear.
    assert described["model"]["name"] == "credit_default_v1_leaky"


def test_unknown_scenario_degrades_without_raising() -> None:
    described = describe(PROJECT_ROOT, "not_a_scenario", bundle={}, run=None, subject="leaked")
    assert described["model"] is None
    assert described["timing"] is None
