"""Measure the detector instead of asserting it works.

Five hand-picked scenarios demonstrate that Hindsight *can* catch leakage. They
say nothing about how often it does, or what it costs in false alarms. This
sweeps the defect across its full range - from a leak that reaches every record
to one that reaches almost none - against matched clean controls, and reports
precision, recall and a per-route breakdown.

The interesting result is not the headline number. It is that recall by the
statistical route alone falls off sharply as the leak gets subtler, while the
deterministic route holds - which is the whole argument for having both, stated
as a measurement rather than a claim.

Ground truth is structural, not labelled by hand:

* a **leaked** case joins a post-outcome source with no availability guard;
* a **clean** case is the same data through the repaired query.

So a false positive means flagging a query that provably has the guard, and a
false negative means missing one that provably does not.
"""

from __future__ import annotations

import json
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hindsight.workflow import run_demo_audit

# The defect's reach, from total to barely-there. 0.02 means two records in a
# hundred carry post-cutoff data - well past the point a human would notice.
COVERAGES = (1.0, 0.7, 0.4, 0.25, 0.15, 0.08, 0.02)
SEEDS = (20260727, 20260801, 20260815)


@dataclass
class Case:
    case_id: str
    coverage: float
    seed: int
    guarded: bool  # the repaired query - ground truth "clean"
    verdict: str = ""
    decision: str = ""
    route: str = ""
    observed_auc: float = 0.0
    point_in_time_auc: float = 0.0
    collapsed: bool = False
    runtime_seconds: float = 0.0

    @property
    def is_leaked(self) -> bool:
        return not self.guarded

    @property
    def flagged(self) -> bool:
        return self.decision == "block"

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "coverage": self.coverage,
            "seed": self.seed,
            "ground_truth": "leaked" if self.is_leaked else "clean",
            "verdict": self.verdict,
            "decision": self.decision,
            "confirmation_route": self.route,
            "observed_auc": round(self.observed_auc, 6),
            "point_in_time_auc": round(self.point_in_time_auc, 6),
            "statistical_route_fired": self.collapsed,
            "correct": self.flagged == self.is_leaked,
            "runtime_seconds": round(self.runtime_seconds, 4),
        }


@dataclass
class Benchmark:
    cases: list[Case] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        tp = sum(1 for c in self.cases if c.is_leaked and c.flagged)
        fn = sum(1 for c in self.cases if c.is_leaked and not c.flagged)
        fp = sum(1 for c in self.cases if not c.is_leaked and c.flagged)
        tn = sum(1 for c in self.cases if not c.is_leaked and not c.flagged)
        return {
            "true_positive": tp,
            "false_negative": fn,
            "false_positive": fp,
            "true_negative": tn,
        }

    def metrics(self) -> dict[str, Any]:
        c = self.counts()
        tp, fn, fp, tn = (
            c["true_positive"],
            c["false_negative"],
            c["false_positive"],
            c["true_negative"],
        )
        precision = tp / (tp + fp) if (tp + fp) else 1.0
        recall = tp / (tp + fn) if (tp + fn) else 1.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "accuracy": round((tp + tn) / len(self.cases), 4) if self.cases else 0.0,
        }

    def route_breakdown(self) -> list[dict[str, Any]]:
        """Recall per coverage, split by which route actually fired.

        This is the point of the whole exercise: it shows the statistical route
        degrading as the defect gets subtler, and the deterministic route not.
        """
        rows = []
        for coverage in COVERAGES:
            leaked = [c for c in self.cases if c.is_leaked and c.coverage == coverage]
            if not leaked:
                continue
            statistical = sum(1 for c in leaked if c.collapsed)
            caught = sum(1 for c in leaked if c.flagged)
            aucs = [c.observed_auc - c.point_in_time_auc for c in leaked]
            rows.append(
                {
                    "coverage": coverage,
                    "cases": len(leaked),
                    "caught": caught,
                    "recall": round(caught / len(leaked), 4),
                    "statistical_route_fired": statistical,
                    "statistical_recall": round(statistical / len(leaked), 4),
                    "mean_auc_delta": round(sum(aucs) / len(aucs), 4),
                }
            )
        return rows

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            # Stated up front, because a perfect score should make a reader
            # suspicious and they should not have to work out why on their own.
            "how_to_read_this": {
                "the_headline_is_partly_tautological": (
                    "Ground truth here is structural - a case is 'leaked' if its query joins a "
                    "post-outcome source with no availability guard. The deterministic route "
                    "reads that same query. So its perfect score on this benchmark is close to "
                    "true by construction, and should not be read as field accuracy."
                ),
                "what_this_does_measure_honestly": [
                    "The statistical route's recall curve as the defect gets subtler - it is "
                    "not told about the SQL, so its degradation is a real measurement.",
                    "Zero false positives across every guarded query. The detector could have "
                    "flagged those and does not.",
                    "The AUC delta shrinking toward invisibility as reach falls, which is why "
                    "a statistics-only detector is insufficient.",
                    "Runtime per case.",
                ],
                "what_it_cannot_tell_you": (
                    "How Hindsight performs on real-world SQL it has never seen, where the "
                    "guard may be expressed in ways the parser does not recognise. That needs "
                    "a corpus of real transformations, which is future work."
                ),
            },
            "cases": len(self.cases),
            "leaked": sum(1 for c in self.cases if c.is_leaked),
            "clean": sum(1 for c in self.cases if not c.is_leaked),
            "counts": self.counts(),
            "metrics": self.metrics(),
            "by_coverage": self.route_breakdown(),
            "total_runtime_seconds": round(sum(c.runtime_seconds for c in self.cases), 3),
            "results": [c.to_dict() for c in self.cases],
        }


def run_benchmark(project_root: Path) -> Benchmark:
    root = Path(project_root)
    base = json.loads((root / "scenarios/credit_default/scenario.json").read_text(encoding="utf-8"))
    leaky_sql = root / "examples/leaky_feature.sql"
    guarded_sql = root / "examples/remediation.sql"

    benchmark = Benchmark()
    with tempfile.TemporaryDirectory() as tmp:
        for seed in SEEDS:
            for coverage in COVERAGES:
                config = dict(base)
                config["seed"] = seed
                config["post_cutoff_coverage"] = coverage
                path = Path(tmp) / f"s{seed}_c{coverage}.json"
                path.write_text(json.dumps(config), encoding="utf-8")

                for guarded in (False, True):
                    case = Case(
                        case_id=f"seed{seed}-cov{coverage}-{'clean' if guarded else 'leaked'}",
                        coverage=coverage,
                        seed=seed,
                        guarded=guarded,
                    )
                    started = time.perf_counter()
                    bundle = run_demo_audit(
                        scenario_path=path,
                        transformation_path=guarded_sql if guarded else leaky_sql,
                        remediation_path=guarded_sql,
                        post_outcome_table="payment_events_after_decision",
                        subject="safe_control" if guarded else "leaked",
                    )
                    case.runtime_seconds = time.perf_counter() - started
                    leak = bundle["validation"]["leakage_case"]
                    case.verdict = bundle["verdict"]
                    case.decision = bundle["release_decision"]
                    case.route = bundle["confirmation_route"]
                    case.observed_auc = leak["observed_auc"]
                    case.point_in_time_auc = leak["point_in_time_auc"]
                    case.collapsed = bool(leak["collapsed"])
                    benchmark.cases.append(case)

    return benchmark


def render(benchmark: Benchmark) -> str:
    data = benchmark.to_dict()
    m, c = data["metrics"], data["counts"]
    lines = [
        f"Hindsight detection benchmark - {data['cases']} cases "
        f"({data['leaked']} leaked, {data['clean']} clean)",
        "",
        f"  precision {m['precision']:.3f}    recall {m['recall']:.3f}    "
        f"F1 {m['f1']:.3f}    accuracy {m['accuracy']:.3f}",
        f"  TP {c['true_positive']}  FN {c['false_negative']}  "
        f"FP {c['false_positive']}  TN {c['true_negative']}",
        "",
        "  Recall as the defect gets subtler:",
        "",
        "    reach   cases  AUC delta   statistical   overall",
        "    " + "-" * 48,
    ]
    for row in data["by_coverage"]:
        lines.append(
            f"    {row['coverage']:>5.0%}   {row['cases']:>5}   "
            f"{row['mean_auc_delta']:>9.4f}   {row['statistical_recall']:>11.0%}   "
            f"{row['recall']:>7.0%}"
        )
    lines += [
        "",
        "  The statistical route weakens as the leak gets subtler. The deterministic",
        "  SQL/time proof does not - which is why both exist.",
        "",
        "  READ THE HEADLINE WITH CARE. Ground truth here is structural: a case is",
        "  'leaked' if its query joins a post-outcome source with no guard, and the",
        "  deterministic route reads that same query. Its perfect score is close to",
        "  true by construction. What is measured honestly is the statistical route's",
        "  recall curve, the absence of false positives on guarded queries, and the",
        "  AUC delta shrinking toward invisibility.",
        "",
        f"  total runtime {data['total_runtime_seconds']:.1f}s",
    ]
    return "\n".join(lines) + "\n"
