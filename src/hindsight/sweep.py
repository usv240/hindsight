"""Audit every candidate feature, then rank them.

Every other entry point answers "is this feature leaking?". That assumes you
already suspect one. A real model has forty features and the honest question is
"which of these is wrong", so this runs the same point-in-time reconstruction
across a whole wide snapshot table and orders the results by how much of each
feature's apparent advantage disappears once the future is removed.

Two things it deliberately does not do:

  * It does not promote anything to `confirmed`. Ranking is triage - it says
    where to look, not what is true. The verdict still comes from the same
    deterministic routes, one feature at a time, because a ranking is a
    comparison and a verdict is a claim about a single artifact.
  * It does not rank by importance. The feature with the largest ablation delta
    is frequently the legitimate one; that is the trap this project exists to
    demonstrate. The ranking key is advantage *lost to the cutoff*, which is a
    different quantity and the only one that indicates a temporal defect.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from hindsight.validation.point_in_time import run_credit_validation


class SweepConfigError(ValueError):
    """The scenario cannot be swept."""


def _candidates(config: dict[str, Any]) -> list[str]:
    adapter = config.get("point_in_time_adapter")
    if not isinstance(adapter, dict) or adapter.get("kind") != "wide_snapshots":
        raise SweepConfigError(
            "sweep requires a scenario whose point_in_time_adapter.kind is 'wide_snapshots'"
        )
    columns = adapter.get("columns", {})
    declared = adapter.get("sweep_features")
    if declared is not None:
        if not isinstance(declared, list) or not all(
            isinstance(name, str) and name.strip() for name in declared
        ):
            raise SweepConfigError("point_in_time_adapter.sweep_features must be a list of names")
        candidates = list(declared)
    else:
        candidates = [columns["feature"]] if columns.get("feature") else []
    if not candidates:
        raise SweepConfigError(
            "declare point_in_time_adapter.sweep_features to name the columns to audit"
        )

    # Auditing the safe control against itself is meaningless: it is the column
    # the reconstruction holds constant as the comparison baseline.
    safe = columns.get("safe_feature")
    return [name for name in candidates if name != safe]


def sweep(config_path: Path) -> dict[str, Any]:
    """Reconstruct every candidate feature and rank by advantage lost."""
    config = json.loads(config_path.read_text(encoding="utf-8"))
    candidates = _candidates(config)

    findings: list[dict[str, Any]] = []
    for name in candidates:
        variant = deepcopy(config)
        variant["point_in_time_adapter"]["columns"]["feature"] = name

        scratch = config_path.parent / f".sweep-{config_path.stem}-{name}.json"
        # Paths inside the scenario are resolved relative to the file, and the
        # scratch file sits beside the original, so they keep resolving.
        try:
            scratch.write_text(json.dumps(variant), encoding="utf-8")
            report = run_credit_validation(scratch)
        except Exception as error:  # noqa: BLE001 - one bad column must not stop the sweep
            findings.append(
                {
                    "feature": name,
                    "status": "could_not_evaluate",
                    "reason": str(error),
                }
            )
            continue
        finally:
            scratch.unlink(missing_ok=True)

        case = report["leakage_case"]
        observed = float(case["observed_advantage"])
        retained = float(case["advantage_retained"])
        findings.append(
            {
                "feature": name,
                "status": "evaluated",
                "observed_auc": round(float(case["observed_auc"]), 6),
                "point_in_time_auc": round(float(case["point_in_time_auc"]), 6),
                "observed_advantage": round(observed, 6),
                "advantage_retained": round(retained, 6),
                "advantage_lost": round(observed * (1.0 - retained), 6),
                "collapsed": bool(case["collapsed"]),
                "excluded_post_cutoff_records": int(
                    report["reconstruction"]["excluded_post_cutoff_records"]
                ),
            }
        )

    evaluated = [item for item in findings if item["status"] == "evaluated"]
    # Largest loss first: the feature whose advantage most depended on records
    # that did not exist yet.
    evaluated.sort(key=lambda item: item["advantage_lost"], reverse=True)
    failed = [item for item in findings if item["status"] != "evaluated"]

    return {
        "schema_version": 1,
        "scenario": config.get("scenario"),
        "candidates": len(candidates),
        "ranked_by": "advantage_lost",
        "how_to_read_this": (
            "Ranking is triage, not a verdict. A feature high in this list had most "
            "of its advantage removed by the cutoff, which is where to look first. "
            "Confirming a defect still requires the deterministic routes, one "
            "feature at a time. Note that ranking by importance would put the "
            "legitimate control near the top instead."
        ),
        "flagged": [item["feature"] for item in evaluated if item["collapsed"]],
        "findings": evaluated + failed,
    }
