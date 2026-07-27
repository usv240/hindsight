"""The cutoff timeline: the one graphic that explains the whole product.

Every other view of leakage is abstract - a path, a verdict, a delta. The defect
itself is temporal: a feature reached across the moment of decision and read
something that did not exist yet. Drawing time literally, with the prediction
cutoff as a hard vertical rule, makes the violation visible before any prose is
read. Data that stays left of the line is knowable; anything a feature pulls from
the right of it is hindsight.

Positions are computed here rather than in the template so the geometry is
testable and the view stays declarative.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

# The window is symmetric around the decision, so one linear time scale places
# the cutoff dead centre. An asymmetric window would need a piecewise scale,
# which would compress one side relative to the other - a distorted axis on a
# graphic whose entire job is to be trusted about time.
CUTOFF_PCT = 50.0
_WINDOW_BEFORE = timedelta(days=45)
_WINDOW_AFTER = timedelta(days=45)


@dataclass
class Track:
    """One row of the timeline: an asset and when its data actually exists."""

    label: str
    column: str
    start_pct: float
    end_pct: float
    kind: str  # "source" | "safe" | "leak"
    note: str = ""
    crosses: bool = False
    reach_pct: float = 0.0
    days_after: int = 0


@dataclass
class Timeline:
    cutoff_pct: float = CUTOFF_PCT
    cutoff_label: str = ""
    tracks: list[Track] = field(default_factory=list)
    ticks: list[dict[str, Any]] = field(default_factory=list)


def build_timeline(bundle: dict[str, Any], scenario: dict[str, Any]) -> Timeline:
    cutoff = _parse(scenario.get("prediction_time")) or datetime(2026, 1, 10, 9, tzinfo=UTC)
    start = cutoff - _WINDOW_BEFORE
    end = cutoff + _WINDOW_AFTER
    span = (end - start).total_seconds()

    def pct(moment: datetime) -> float:
        return round(max(0.0, min(100.0, (moment - start).total_seconds() / span * 100)), 2)

    # The planted defect reaches this far past the decision. Sourced from the
    # audit rather than hardcoded so the drawing cannot drift from the evidence.
    days_after = _days_after(bundle, default=31)
    leak_reach = cutoff + timedelta(days=days_after)

    tracks = [
        Track(
            label="applications_at_decision_time",
            column="prediction_time",
            start_pct=pct(start),
            end_pct=CUTOFF_PCT,
            kind="source",
            note="the decision itself",
        ),
        Track(
            label="customer_history_point_in_time",
            column="prior_delinquencies",
            start_pct=pct(start),
            end_pct=CUTOFF_PCT,
            kind="source",
            note="entirely pre-cutoff",
        ),
        Track(
            label="feature_pipeline_safe",
            column="prior_delinquencies",
            start_pct=pct(start + timedelta(days=6)),
            end_pct=CUTOFF_PCT,
            kind="safe",
            note="stops at the cutoff - cleared for release",
        ),
        Track(
            label="feature_pipeline_leaky",
            column="days_since_last_payment",
            start_pct=pct(start + timedelta(days=6)),
            end_pct=CUTOFF_PCT,
            kind="leak",
            crosses=True,
            reach_pct=pct(leak_reach),
            days_after=days_after,
            note=f"reaches {days_after} days past the decision",
        ),
    ]

    ticks = []
    for offset in (-40, -20, 0, 20, 40):
        moment = cutoff + timedelta(days=offset)
        ticks.append(
            {
                "pct": pct(moment),
                "label": "decision" if offset == 0 else f"{offset:+d}d",
                "is_cutoff": offset == 0,
            }
        )

    return Timeline(
        cutoff_pct=CUTOFF_PCT,
        cutoff_label=cutoff.strftime("%d %b %Y"),
        tracks=tracks,
        ticks=ticks,
    )


def _days_after(bundle: dict[str, Any], default: int) -> int:
    """Recover the violation size from the audit when it is recorded there."""
    for candidate in (
        bundle.get("sql_verification", {}).get("days_after"),
        bundle.get("validation", {}).get("days_after"),
    ):
        if isinstance(candidate, int | float) and candidate > 0:
            return int(candidate)
    return default


def _parse(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)
