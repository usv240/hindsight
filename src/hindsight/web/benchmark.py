"""Shape the committed benchmark for the evidence page.

This is the project's strongest measurement and it was visible only in the README
and a JSON file. Someone who watches the video and clicks the demo never saw it.

The chart it feeds is deliberately part-to-whole rather than two lines. Every case
caught by the statistical route is also caught overall, so they are not
independent series - the honest encoding is one bar per reach band, always full,
whose composition shifts from "statistics found it" to "only the deterministic
proof found it". The bar staying full while one segment vanishes *is* the
argument for two routes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load(project_root: Path) -> dict[str, Any] | None:
    """Read the committed sweep, or None if it has not been run."""
    path = project_root / "evaluations" / "benchmark.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None

    bands = payload.get("by_coverage")
    counts = payload.get("counts")
    if not isinstance(bands, list) or not bands or not isinstance(counts, dict):
        return None

    rows: list[dict[str, Any]] = []
    for band in bands:
        if not isinstance(band, dict):
            continue
        cases = int(band.get("cases") or 0)
        if not cases:
            continue
        statistical = int(band.get("statistical_route_fired") or 0)
        caught = int(band.get("caught") or 0)
        rows.append(
            {
                "reach_pct": round(float(band.get("coverage", 0.0)) * 100),
                "cases": cases,
                "statistical": statistical,
                # Cases the statistics missed and the deterministic route caught.
                "deterministic_only": max(0, caught - statistical),
                "missed": max(0, cases - caught),
                "statistical_pct": round(statistical / cases * 100),
                "deterministic_only_pct": round(max(0, caught - statistical) / cases * 100),
                "auc_delta": round(float(band.get("mean_auc_delta") or 0.0), 4),
                "statistical_fired": statistical > 0,
            }
        )

    if not rows:
        return None

    # Where the statistical route stops firing, read from the data rather than
    # written down, so the caption cannot drift from the measurement.
    blind_from = next((row["reach_pct"] for row in rows if not row["statistical_fired"]), None)
    faintest = rows[-1]

    return {
        "rows": rows,
        "cases": sum(row["cases"] for row in rows),
        "false_positives": int(counts.get("false_positive", 0)),
        "false_negatives": int(counts.get("false_negative", 0)),
        "clean_cases": int(counts.get("true_negative", 0)),
        "blind_from_pct": blind_from,
        "faintest": faintest,
        "how_to_read_this": payload.get("how_to_read_this"),
    }
