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
_DEFAULT_CUTOFF = datetime(2026, 1, 10, 9, tzinfo=UTC)
# Leave room for the window on both sides of the representable range.
_EARLIEST = datetime.min.replace(year=2, tzinfo=UTC)
_LATEST = datetime.max.replace(year=9998, tzinfo=UTC)


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
    cutoff = _parse(scenario.get("prediction_time")) or _DEFAULT_CUTOFF
    # datetime.min/max are only a few days from the representable edge, so the
    # window arithmetic below overflows on absurd - but parseable - timestamps.
    cutoff = min(max(cutoff, _EARLIEST), _LATEST)
    start = cutoff - _WINDOW_BEFORE
    end = cutoff + _WINDOW_AFTER
    span = (end - start).total_seconds()

    def pct(moment: datetime) -> float:
        return round(max(0.0, min(100.0, (moment - start).total_seconds() / span * 100)), 2)

    # The planted defect reaches this far past the decision. Sourced from the
    # audit rather than hardcoded so the drawing cannot drift from the evidence.
    days_after = _days_after(bundle, default=31)
    leak_reach = cutoff + timedelta(days=days_after)

    context = bundle.get("validation", {}).get("evidence_context", {})
    decision_asset, decision_column = _split_node(
        context.get("decision_node"), "applications_at_decision_time.prediction_time"
    )
    safe_path = context.get("safe_lineage_path", [])
    leakage_path = context.get("leakage_lineage_path", [])
    safe_source_asset, safe_source_column = _split_node(
        safe_path[0] if safe_path else None,
        "customer_history_point_in_time.prior_delinquencies",
    )
    safe_feature_asset, safe_feature_column = _split_node(
        safe_path[-1] if safe_path else None,
        "feature_pipeline_safe.prior_delinquencies",
    )
    leak_feature_asset, leak_feature_column = _split_node(
        leakage_path[-1] if leakage_path else None,
        "feature_pipeline_leaky.days_since_last_payment",
    )

    tracks = [
        Track(
            label=decision_asset,
            column=decision_column,
            start_pct=pct(start),
            end_pct=CUTOFF_PCT,
            kind="source",
            note="the decision itself",
        ),
        Track(
            label=safe_source_asset,
            column=safe_source_column,
            start_pct=pct(start),
            end_pct=CUTOFF_PCT,
            kind="source",
            note="entirely pre-cutoff",
        ),
        Track(
            label=safe_feature_asset,
            column=safe_feature_column,
            start_pct=pct(start + timedelta(days=6)),
            end_pct=CUTOFF_PCT,
            kind="safe",
            note="stops at the cutoff - cleared for release",
        ),
        Track(
            label=leak_feature_asset,
            column=leak_feature_column,
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
        bundle.get("validation", {})
        .get("evidence_context", {})
        .get("leakage_available_offset_days"),
    ):
        if isinstance(candidate, int | float) and candidate > 0:
            return int(candidate)
    return default


def _split_node(value: Any, fallback: str) -> tuple[str, str]:
    node = value if isinstance(value, str) and "." in value else fallback
    return tuple(node.rsplit(".", 1))  # type: ignore[return-value]


def _parse(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)
