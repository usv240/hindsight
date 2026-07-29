"""The identity panel answers "a verdict about what, exactly".

Its failure mode is not a crash, it is confidently naming the wrong artifact.
A page that shows the leaky model's URN above a clean verdict, or calls a
legitimate pre-cutoff fact "the whole defect", is worse than one that says
nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

from hindsight.web.subject import describe

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUNDLE = {"validation": {"rows": 4000}, "audit_config": {"synthetic": True}}
RUN = {"started_at": "2026-07-29T16:28:16Z", "run_id": "20260729T162816-ce1cd1"}


CONTEXT = json.loads(
    (PROJECT_ROOT / "fixtures/credit_default/ground_truth.json").read_text(encoding="utf-8")
)


def _bundle(prefix: str, model: str, feature: str) -> dict:
    """A bundle shaped like the real one, carrying per-scenario URNs."""
    return {
        "validation": {
            "rows": 4000,
            "evidence_context": {
                f"{prefix}model_urn": model,
                f"{prefix}feature_urn": feature,
            },
        },
        "audit_config": {"synthetic": True},
    }


def _facts(subject: str) -> dict[str, dict[str, str]]:
    described = describe(PROJECT_ROOT, "credit_default", bundle=BUNDLE, run=RUN, subject=subject)
    return {fact["label"]: fact for fact in described["facts"]}


def test_names_the_model_rather_than_saying_this_model() -> None:
    facts = _facts("leaked")
    assert facts["Model under audit"]["value"] == "credit_default_v1_leaky"
    assert facts["Model under audit"]["detail"].startswith("urn:li:mlModel:")


def test_the_safe_control_is_a_different_model() -> None:
    """Showing the leaky model above a clean verdict would be a lie."""
    leaked = _facts("leaked")["Model under audit"]["value"]
    safe = _facts("safe_control")["Model under audit"]["value"]
    assert leaked != safe
    assert safe == "credit_default_v2_safe"


def test_the_safe_control_examines_a_different_feature() -> None:
    assert _facts("leaked")["Feature examined"]["value"] == "days_since_last_payment"
    assert _facts("safe_control")["Feature examined"]["value"] == "prior_delinquencies"


def test_feature_row_names_the_table_it_lives_in() -> None:
    assert _facts("leaked")["Feature examined"]["detail"] == "in feature_pipeline_leaky"


def test_a_post_cutoff_fact_is_called_late_and_a_pre_cutoff_one_is_not() -> None:
    late = _facts("leaked")["That fact became knowable"]
    fine = _facts("safe_control")["That fact became knowable"]

    assert late["detail"] == "31 days too late"
    assert late["note"] == "The gap is the whole defect"

    # The identical row on a clean audit must not contradict the verdict.
    assert "too late" not in fine["detail"]
    assert fine["detail"] == "1 day before the decision"
    assert fine["note"] == "Already knowable, so legitimate to use"


def test_urns_are_the_ones_the_audit_actually_used() -> None:
    """Display must not drift from the fixture the lineage was resolved against."""
    truth = json.loads(
        (PROJECT_ROOT / "fixtures/credit_default/ground_truth.json").read_text(encoding="utf-8")
    )
    described = describe(PROJECT_ROOT, "credit_default", bundle=BUNDLE, run=RUN, subject="leaked")
    assert described["model_urn"] == truth["model_urn"]
    assert described["feature_urn"] == truth["feature_urn"]


def test_synthetic_data_is_disclosed_beside_realistic_looking_urns() -> None:
    assert describe(PROJECT_ROOT, "credit_default", bundle=BUNDLE, run=RUN, subject="leaked")[
        "synthetic"
    ]


def test_missing_run_drops_rows_rather_than_inventing_them() -> None:
    described = describe(PROJECT_ROOT, "credit_default", bundle={}, run=None, subject="leaked")
    labels = [fact["label"] for fact in described["facts"]]
    assert "Audited" not in labels
    assert "Records re-tested" not in labels
    # Identity still resolves; only the run-scoped rows disappear.
    assert "Model under audit" in labels


def test_unknown_scenario_degrades_without_raising() -> None:
    described = describe(PROJECT_ROOT, "not_a_scenario", bundle=BUNDLE, run=RUN, subject="leaked")
    assert isinstance(described["facts"], list)


# --- The regression that made all of this necessary -------------------------
#
# The first version read fixtures/<slug>/ground_truth.json and fell back to
# fixtures/credit_default when a scenario had no fixture of its own. Only
# credit_default has one, so every scenario rendered the credit model: a fraud
# audit claimed to examine days_since_last_payment on credit_default_v1_leaky.
# The tests above all passed, because they only ever exercised credit_default.


def _live(slug: str) -> dict[str, dict[str, str]]:
    """Describe a scenario the way the app does, from its real config and run."""
    import glob

    from hindsight.web.app import _audit_config

    config = _audit_config(PROJECT_ROOT, slug)
    scenario = json.loads(Path(config.scenario_path).read_text(encoding="utf-8"))
    for path in sorted(glob.glob(str(PROJECT_ROOT / "evidence/runs/*.json")), reverse=True):
        run = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(run, dict) or (run.get("scenario") or run.get("audit")) != slug:
            continue
        described = describe(
            PROJECT_ROOT,
            Path(config.scenario_path).parent.name,
            bundle=run.get("evidence_bundle") or {},
            run=run,
            subject=config.subject,
            scenario_cutoff=scenario.get("prediction_time", ""),
        )
        return {fact["label"]: fact for fact in described["facts"]}
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
        facts = _live(slug)
        assert facts["Model under audit"]["value"] == model, slug
        assert facts["Feature examined"]["value"] == feature, slug


def test_no_two_scenario_families_share_a_model() -> None:
    """The bug was every scenario showing one model. Assert they are distinct."""
    models = {
        slug: _live(slug)["Model under audit"]["value"]
        for slug in ("credit_default", "fraud_screening", "hospital_readmission")
    }
    assert len(set(models.values())) == 3, models


def test_every_scenario_reports_its_own_reach() -> None:
    """9, 22 and 31 days are different defects; one number for all would be a tell."""
    reaches = {
        slug: _live(slug)["That fact became knowable"]["detail"]
        for slug in ("credit_default", "fraud_screening", "hospital_readmission")
    }
    assert all("too late" in value for value in reaches.values()), reaches
    assert len(set(reaches.values())) == 3, reaches


def test_a_scenario_without_a_fixture_still_gets_every_row() -> None:
    """Dates come from the scenario definition and bundle, not only the fixture."""
    assert len(_live("fraud_screening")) == len(_live("credit_default"))
