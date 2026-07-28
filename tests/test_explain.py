"""A visitor with no ML background must be able to follow the whole argument.

These tests guard comprehension, not correctness of the maths: that the page
leads with a conclusion in ordinary words, that every scenario is genuinely
runnable, and that plain language never replaces the exact figures.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hindsight.config import AuditConfig
from hindsight.scenarios import SCENARIOS, get_scenario, list_scenarios
from hindsight.web import create_app
from hindsight.web.explain import explain, plain_score, score_sentence
from hindsight.web.runs import record_run

JARGON = ["auc", "ablation", "point-in-time", "lineage", "urn:", "verdict"]


def _bundle(blocked: bool = True) -> dict:
    return {
        "release_decision": "block" if blocked else "clear",
        "validation": {
            "leakage_case": {
                "observed_auc": 1.0,
                "point_in_time_auc": 0.8336,
                "advantage_retained": 0.4486,
            },
            "safe_control": {"observed_auc": 0.9248},
        },
    }


# -- Plain language ---------------------------------------------------------


@pytest.mark.parametrize(
    ("auc", "expected"),
    [(1.0, "perfect"), (0.93, "very strong"), (0.83, "solid"), (0.72, "useful"), (0.4, None)],
)
def test_scores_get_an_everyday_label(auc: float, expected: str | None) -> None:
    label = plain_score(auc)
    assert label
    if expected:
        assert label == expected


def test_score_sentences_avoid_statistics_vocabulary() -> None:
    for auc in (1.0, 0.9, 0.83, 0.72, 0.61, 0.4):
        sentence = score_sentence(auc).lower()
        assert "auc" not in sentence
        assert "roc" not in sentence


def test_the_headline_states_the_conclusion_in_ordinary_words() -> None:
    plain = explain(_bundle(), get_scenario("credit_default").to_dict())
    assert plain["headline"] == "This model was cheating."
    for word in JARGON:
        assert word not in plain["headline"].lower()


def test_a_clean_model_is_not_described_as_cheating() -> None:
    plain = explain(_bundle(blocked=False), get_scenario("credit_default").to_dict())
    assert "cheating" not in plain["headline"].lower()
    assert plain["what_now"] == ["This version is clear to release."]


def test_the_analogy_is_mapped_onto_the_chosen_scenario() -> None:
    scenario = get_scenario("hospital_readmission")
    plain = explain(_bundle(), scenario.to_dict())
    mapped = dict(plain["analogy"]["mapping"])
    assert mapped["The exam"] == scenario.question
    assert mapped["The answer sheet"] == scenario.leak_plain


def test_next_steps_are_actions_a_person_can_take() -> None:
    plain = explain(_bundle(), get_scenario("credit_default").to_dict())
    assert len(plain["what_now"]) == 3
    assert "Do not release" in plain["what_now"][0]


# -- Scenario library -------------------------------------------------------


def test_every_scenario_is_actually_runnable() -> None:
    """A scenario offered in the picker must have real data and SQL behind it."""
    root = Path.cwd()
    for scenario in list_scenarios():
        config = AuditConfig.load(root / scenario.audit_config, root)
        config.validate()
        assert config.scenario_path.exists(), scenario.slug
        assert config.transformation_path.exists(), scenario.slug
        assert config.remediation_path.exists(), scenario.slug


def test_every_scenario_tells_a_human_story() -> None:
    for scenario in list_scenarios():
        assert len(scenario.story) >= 3, scenario.slug
        for beat in scenario.story:
            assert beat["when"] and beat["what"] and beat["note"], scenario.slug
        for text in (scenario.situation, scenario.question, scenario.stakes):
            assert text.strip().endswith(("?", ".")), scenario.slug


def test_scenarios_are_told_without_jargon() -> None:
    for scenario in list_scenarios():
        blurb = f"{scenario.situation} {scenario.question} {scenario.leak_plain}".lower()
        for word in ("auc", "ablation", "lineage", "urn", "schema"):
            assert word not in blurb, f"{scenario.slug} leaks jargon: {word}"


def test_scenarios_use_distinct_data_so_results_differ() -> None:
    import json

    seeds = set()
    for scenario in list_scenarios():
        config = AuditConfig.load(Path.cwd() / scenario.audit_config, Path.cwd())
        seeds.add(json.loads(config.scenario_path.read_text(encoding="utf-8"))["seed"])
    assert len(seeds) == len(SCENARIOS), "each scenario needs its own seed"


def test_an_unknown_scenario_falls_back_rather_than_failing() -> None:
    assert get_scenario("does-not-exist").slug == "credit_default"
    assert get_scenario(None).slug == "credit_default"


# -- Rendered page ----------------------------------------------------------


def test_the_overview_offers_every_scenario() -> None:
    text = TestClient(create_app(Path.cwd())).get("/").text
    for scenario in list_scenarios():
        assert scenario.name in text
        assert scenario.question in text


def test_the_detail_page_leads_with_plain_english() -> None:
    client = TestClient(create_app(Path.cwd()))
    run = record_run(Path.cwd(), client.get("/api/audit").json())
    text = client.get(f"/audits/{run['run_id']}").text

    assert "This model was cheating" in text
    assert "answer sheet" in text
    assert 'class="mode-switch"' in text
    assert 'data-mode="plain"' in text
    # Technical evidence is present but hidden until asked for.
    assert 'class="tech-only"' in text
    assert "1.000000" in text


def test_switching_scenario_changes_the_story_on_the_page() -> None:
    client = TestClient(create_app(Path.cwd()))
    run = record_run(Path.cwd(), client.get("/api/audit").json())
    text = client.get(f"/audits/{run['run_id']}?scenario=fraud_screening").text
    assert "Is this transaction fraudulent?" in text
    assert "disputes" in text.lower()


def test_the_story_names_the_post_outcome_source_not_the_feature() -> None:
    """A screenshot caught this naming the feature as its own source."""
    from fastapi.testclient import TestClient

    from hindsight.web import create_app
    from hindsight.web.runs import record_run

    client = TestClient(create_app(Path.cwd()))
    run = record_run(Path.cwd(), client.get("/api/audit").json())
    text = client.get(f"/audits/{run['run_id']}").text

    start = text.find("HOW HINDSIGHT KNEW")
    if start == -1:
        start = text.find("How Hindsight knew")
    block = text[start : start + 1400]
    assert "payment_events_after_decision" in block
    assert "feature_pipeline_leaky" not in block
