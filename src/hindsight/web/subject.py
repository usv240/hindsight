"""What is actually under audit.

The console delivered a verdict on "this model" without ever saying which model,
which of its features, or as of when. For a demo that reads as vague; for a
release gate it is the difference between an audit record and an anecdote. A
reviewer's first question is always "of what, exactly".

Everything here is read from the recorded ground-truth fixture and the scenario
definition. Nothing is invented for display: the model and feature URNs are the
same ones the audit resolved lineage against, and the two timestamps are the ones
the temporal check compares. If a field is missing the row is dropped rather than
filled in, because a plausible-looking identifier is worse than an absent one.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _read(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _name_from_urn(urn: str) -> str:
    """Last meaningful segment of a URN, for display beside the full value.

    ``urn:li:mlModel:hindsight.credit_default_v1_leaky`` -> ``credit_default_v1_leaky``
    ``urn:li:schemaField:(hindsight.feature_pipeline_leaky,days_since_last_payment)``
        -> ``days_since_last_payment``
    """
    if not urn:
        return ""
    if urn.endswith(")") and "," in urn:
        return urn.rsplit(",", 1)[-1].rstrip(")")
    return urn.rsplit(":", 1)[-1].rsplit(".", 1)[-1]


def _dataset_from_field_urn(urn: str) -> str:
    """The table a schemaField URN belongs to, without its platform prefix."""
    if "(" not in urn or "," not in urn:
        return ""
    inner = urn.split("(", 1)[1].rsplit(",", 1)[0]
    return inner.rsplit(".", 1)[-1] if "." in inner else inner


def _human_time(value: str) -> str:
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return value
    return moment.strftime("%d %b %Y, %H:%M UTC")


def _plural(count: int, word: str) -> str:
    """Naive plural, adequate for the handful of nouns this module renders."""
    return word if abs(count) == 1 else word + "s"


def _days_between(later: str, earlier: str) -> int | None:
    try:
        end = datetime.fromisoformat(later.replace("Z", "+00:00"))
        start = datetime.fromisoformat(earlier.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return (end - start).days


def describe(
    project_root: Path,
    scenario_slug: str,
    *,
    bundle: dict[str, Any],
    run: dict[str, Any] | None,
    subject: str = "leaked",
) -> dict[str, Any]:
    """Identity of the audited artifact, for the header of the audit page.

    ``subject`` follows the audit config: a scenario auditing its safe control
    describes a different model to the one auditing the planted defect, and
    showing the leaky model's identity above a clean verdict would be a lie.
    """
    fixture_dir = project_root / "fixtures" / scenario_slug.split("_")[0]
    # Scenario slugs like credit_default_fixed share the base fixture.
    for candidate in (
        project_root / "fixtures" / scenario_slug,
        project_root / "fixtures" / "credit_default",
        fixture_dir,
    ):
        truth = _read(candidate / "ground_truth.json")
        if truth:
            break
    else:  # pragma: no cover - defensive
        truth = {}

    # The safe control is a different model with its own URNs, nested one level
    # down. Auditing it and showing the leaky model's name would be wrong.
    if subject != "leaked" and isinstance(truth.get("safe_control"), dict):
        truth = {**truth, **truth["safe_control"]}

    model_urn = str(truth.get("model_urn") or "")
    feature_urn = str(truth.get("feature_urn") or "")
    cutoff = str(truth.get("prediction_time") or "")
    available = str(truth.get("source_available_at") or "")

    facts: list[dict[str, str]] = []

    if model_urn:
        facts.append(
            {
                "label": "Model under audit",
                "value": _name_from_urn(model_urn),
                "detail": model_urn,
                "note": "The version being considered for release",
            }
        )
    if feature_urn:
        dataset = _dataset_from_field_urn(feature_urn)
        facts.append(
            {
                "label": "Feature examined",
                "value": _name_from_urn(feature_urn),
                "detail": f"in {dataset}" if dataset else feature_urn,
                "note": "One column out of everything the model was shown",
            }
        )
    if cutoff:
        facts.append(
            {
                "label": "Decision moment",
                "value": _human_time(cutoff),
                "detail": "",
                "note": "Nothing after this instant was knowable",
            }
        )
    if available:
        gap = _days_between(available, cutoff) if cutoff else None
        # The same row means opposite things either side of the cutoff. On a
        # clean audit it is the reason the feature is legitimate, so calling it
        # "the whole defect" there would contradict the verdict beside it.
        late = gap is not None and gap > 0
        facts.append(
            {
                "label": "That fact became knowable",
                "value": _human_time(available),
                "detail": (
                    f"{gap} {_plural(gap, 'day')} too late"
                    if late
                    else f"{abs(gap)} {_plural(gap, 'day')} before the decision"
                    if gap is not None
                    else ""
                ),
                "note": (
                    "The gap is the whole defect"
                    if late
                    else "Already knowable, so legitimate to use"
                ),
            }
        )

    validation = bundle.get("validation") or {}
    rows = validation.get("rows") or (run or {}).get("rows")
    if rows:
        facts.append(
            {
                "label": "Records re-tested",
                "value": f"{int(rows):,}",
                "detail": "",
                "note": "Rebuilt as the data looked on the day",
            }
        )

    started = str((run or {}).get("started_at") or "")
    if started:
        facts.append(
            {
                "label": "Audited",
                "value": _human_time(started),
                "detail": (run or {}).get("run_id", ""),
                "note": "This record, not a cached one",
            }
        )

    return {
        "facts": facts,
        "model_urn": model_urn,
        "feature_urn": feature_urn,
        # Synthetic data is disclosed everywhere else in this project; the one
        # place it must not be omitted is beside an identifier that looks real.
        "synthetic": bool((bundle.get("audit_config") or {}).get("synthetic", True)),
    }
