"""Turn the audit's numbers into sentences a non-specialist can act on.

The console was written for people who already know what an AUC is. Everyone
else met `observed_auc 1.000000 -> 0.833630` and `advantage_retained 0.44858`
and had no way in. Nothing here changes a measurement; it restates each one in
plain language and keeps the exact figure alongside, so the page is readable
without ML background and still precise for a reviewer who wants the number.

The governing analogy is an exam. A model that scores perfectly because it saw
the answer sheet is not clever, and everybody already understands why.
"""

from __future__ import annotations

from typing import Any


# AUC is "given one good case and one bad case, how often does the model rank
# them correctly?" That framing is exact and needs no statistics background.
def score_sentence(auc: float) -> str:
    if auc >= 0.995:
        return "Sorted every single case correctly - a perfect score."
    if auc >= 0.9:
        return f"Sorted about {round(auc * 100)} out of 100 pairs correctly - very strong."
    if auc >= 0.8:
        return f"Sorted about {round(auc * 100)} out of 100 pairs correctly - solid."
    if auc >= 0.7:
        return f"Sorted about {round(auc * 100)} out of 100 pairs correctly - useful."
    if auc >= 0.6:
        return f"Sorted about {round(auc * 100)} out of 100 pairs correctly - weak."
    return "Barely better than guessing."


def plain_score(auc: float) -> str:
    """A short label for a score, for use next to the figure."""
    if auc >= 0.995:
        return "perfect"
    if auc >= 0.9:
        return "very strong"
    if auc >= 0.8:
        return "solid"
    if auc >= 0.7:
        return "useful"
    if auc >= 0.6:
        return "weak"
    return "no better than guessing"


def explain(bundle: dict[str, Any], scenario_story: dict[str, str]) -> dict[str, Any]:
    """Build the plain-language reading of one audit."""
    leakage = bundle["validation"]["leakage_case"]
    safe = bundle["validation"]["safe_control"]
    blocked = bundle["release_decision"] == "block"

    observed = leakage["observed_auc"]
    honest = leakage["point_in_time_auc"]
    lost_pct = round((1 - leakage["advantage_retained"]) * 100)

    return {
        # The headline a newcomer reads first.
        "headline": (
            "This model was cheating." if blocked else "This model earned its score honestly."
        ),
        "subhead": (
            f"It scored {plain_score(observed)} in testing. When we rebuilt it using only "
            f"information that existed at decision time, it dropped to {plain_score(honest)}. "
            f"About {lost_pct}% of its apparent skill came from seeing the future."
            if blocked
            else "Its score held up when we removed everything it should not have known."
        ),
        "analogy": {
            "title": "The simplest way to think about it",
            "body": (
                "Imagine a student who aces a practice exam. Impressive - until you notice "
                "the answer sheet was sitting on the desk. The score was real; the ability "
                "was not. Retake the exam without the answers and you learn what they "
                "actually know."
            ),
            "mapping": [
                ("The exam", scenario_story["question"]),
                ("The answer sheet", scenario_story["leak_plain"]),
                ("Retaking it fairly", "Rebuild the data as it looked on the day, then re-test"),
            ],
        },
        "scores": {
            "observed": {
                "value": observed,
                "label": plain_score(observed),
                "sentence": score_sentence(observed),
                "caption": "What the model scored in testing",
            },
            "honest": {
                "value": honest,
                "label": plain_score(honest),
                "sentence": score_sentence(honest),
                "caption": "What it scores once the cheating is removed",
            },
            "control": {
                "value": safe["observed_auc"],
                "label": plain_score(safe["observed_auc"]),
                "sentence": score_sentence(safe["observed_auc"]),
                "caption": "A genuinely good feature, for comparison",
            },
        },
        "lost_pct": lost_pct,
        "kept_pct": 100 - lost_pct,
        "what_now": (
            [
                "Do not release this model version.",
                scenario_story["fix_plain"],
                "Re-run the audit; the score you get then is the real one.",
            ]
            if blocked
            else ["This version is clear to release."]
        ),
        "why_it_matters": scenario_story["stakes"],
    }


# Every technical term that appears on screen, with the everyday phrase that
# replaces it in plain mode.
PLAIN_TERMS: dict[str, str] = {
    "AUC": "score",
    "ablation delta": "how much the model needs this feature",
    "point-in-time reconstruction": "rebuilding the data as it looked on the day",
    "advantage retained": "how much of the skill was real",
    "target leakage": "the model saw the answer",
    "post-outcome": "information from after the decision",
    "prediction cutoff": "the moment the decision had to be made",
    "column-level lineage": "a map of which data fed which data",
    "confirmed": "proven to be cheating",
    "clear_for_release": "safe to ship",
    "needs_review": "a person should look at this",
}
