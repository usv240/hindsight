"""What is actually under audit.

The console delivered a verdict on "this model" without ever saying which model,
which of its features, or as of when. For a demo that reads as vague; for a
release gate it is the difference between an audit record and an anecdote. A
reviewer's first question is always "of what, exactly".

Everything here comes from the evidence bundle the audit produced, which carries
its own ``validation.evidence_context``. That matters: the first version of this
module read ``fixtures/<scenario>/ground_truth.json`` and fell back to
``fixtures/credit_default`` when a scenario had no fixture of its own. Only
credit_default has one, so every scenario displayed the credit model - a fraud
audit claimed to examine ``days_since_last_payment`` on
``credit_default_v1_leaky``. Confidently naming the wrong artifact is worse than
naming none, so there is no cross-scenario fallback any more.

If a field is absent its row is dropped rather than filled in.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from hindsight.web.timeline import _days_after


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


def _parse(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


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
    scenario_family: str,
    *,
    bundle: dict[str, Any],
    run: dict[str, Any] | None,
    subject: str = "leaked",
    scenario_cutoff: str = "",
) -> dict[str, Any]:
    """Identity of the audited artifact, for the header of the audit page.

    ``scenario_family`` is the directory the audit config's scenario path points
    at, not the URL slug. ``credit_default_fixed`` audits the ``credit_default``
    scenario, so it legitimately shares that fixture; ``fraud_screening`` has no
    fixture and must get nothing rather than somebody else's. Taking it from the
    declared config makes that distinction structural instead of a guess.

    ``subject`` follows the audit config: a scenario auditing its safe control
    describes a different model to the one auditing the planted defect, and
    showing the leaky model's identity above a clean verdict would be a lie.
    """
    # The bundle is per-run and per-scenario, so it cannot name another
    # scenario's model. The scenario's own fixture is consulted only for the
    # timestamps the bundle does not carry, and never another scenario's.
    context = ((bundle.get("validation") or {}).get("evidence_context")) or {}
    truth = _read(project_root / "fixtures" / scenario_family / "ground_truth.json")

    leaked = subject == "leaked"
    prefix = "leakage_" if leaked else "safe_"

    if not leaked and isinstance(truth.get("safe_control"), dict):
        truth = {**truth, **truth["safe_control"]}

    model_urn = str(context.get(f"{prefix}model_urn") or truth.get("model_urn") or "")
    feature_urn = str(context.get(f"{prefix}feature_urn") or truth.get("feature_urn") or "")

    # Only credit_default ships a ground-truth fixture, but every scenario
    # defines prediction_time and every bundle records how far the defect
    # reaches. Deriving both from the same source the timeline chart uses means
    # the panel and the chart on one page cannot contradict each other.
    cutoff = str(scenario_cutoff or truth.get("prediction_time") or "")
    available = str(truth.get("source_available_at") or "")
    if not available and cutoff and leaked:
        moment = _parse(cutoff)
        if moment is not None:
            available = (moment + timedelta(days=_days_after(bundle, default=31))).isoformat()

    gap = _days_between(available, cutoff) if (available and cutoff) else None
    late = gap is not None and gap > 0

    # Grouped rather than a flat list of six equal cells. A reader wants three
    # things in order: what the artifact is, when the line was drawn, and only
    # then the bookkeeping about this particular run.
    model = (
        {
            "name": _name_from_urn(model_urn),
            "urn": model_urn,
            "note": "The version being considered for release",
        }
        if model_urn
        else None
    )

    feature = (
        {
            "name": _name_from_urn(feature_urn),
            "table": _dataset_from_field_urn(feature_urn),
            "urn": feature_urn,
            "note": "One column out of everything the model was shown",
        }
        if feature_urn
        else None
    )

    timing = None
    if cutoff:
        timing = {
            "cutoff": _human_time(cutoff),
            "available": _human_time(available) if available else "",
            "gap_days": abs(gap) if gap is not None else None,
            "gap_label": (
                f"{abs(gap)} {_plural(gap, 'day')} too late"
                if late
                else f"{abs(gap)} {_plural(gap, 'day')} earlier"
                if gap is not None
                else ""
            ),
            "late": late,
            # One sentence a reader can take away without parsing the diagram.
            "summary": (
                "The feature reached past the moment the decision was made."
                if late
                else "Everything the feature used was already knowable."
            ),
        }

    meta: list[dict[str, str]] = []
    validation = bundle.get("validation") or {}
    rows = validation.get("rows") or (run or {}).get("rows")
    if rows:
        meta.append({"label": "Records re-tested", "value": f"{int(rows):,}"})
    started = str((run or {}).get("started_at") or "")
    if started:
        meta.append({"label": "Audited", "value": _human_time(started)})
    run_id = (run or {}).get("run_id")
    if run_id:
        meta.append({"label": "Run", "value": str(run_id)})

    return {
        "model": model,
        "feature": feature,
        "timing": timing,
        "meta": meta,
        "model_urn": model_urn,
        "feature_urn": feature_urn,
        # Synthetic data is disclosed everywhere else in this project; the one
        # place it must not be omitted is beside an identifier that looks real.
        "synthetic": bool((bundle.get("audit_config") or {}).get("synthetic", True)),
    }
