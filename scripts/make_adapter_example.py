"""Generate the worked adapter example: subscription churn, not credit.

The point of this example is to be nothing like the built-in scenarios. Different
domain, different column names, different file layout, a different leak mechanism
- so running it proves the adapter reads *someone else's* data rather than a
renamed copy of the demo.

The leak is the realistic one for churn work. `plan_changes_to_date` is a running
count of plan changes, and the training table joins in every change ever recorded
- including the downgrade a customer makes while cancelling. Before the retention
decision that count is close to noise; after it, it is nearly the label.

The safe control is a separate quantity on purpose. An earlier draft used the
pre-decision value of the leaky feature itself, which made the two perfectly
collinear: the honest rebuild scored just as well, so nothing collapsed and the
example quietly proved nothing. Support-ticket volume is a strong, legitimate,
independent driver, which is what the ablation trap needs to have any force.

Deterministic: fixed seed, committed output. Regenerate with
    uv run python scripts/make_adapter_example.py
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

SEED = 20260730
OUT = Path(__file__).resolve().parents[1] / "examples" / "adapter"
DECISION_DAY = datetime(2026, 3, 2, 8, 0, 0)
TRAIN_ROWS = 900
TEST_ROWS = 300


def main() -> int:
    rng = np.random.default_rng(SEED)
    total = TRAIN_ROWS + TEST_ROWS
    OUT.mkdir(parents=True, exist_ok=True)

    tenure_months = rng.integers(1, 72, size=total).astype(float)
    monthly_spend = np.round(rng.normal(58.0, 19.0, size=total).clip(5.0), 2)

    # The safe control: strong, legitimate, entirely pre-decision, and not the
    # same quantity as the leaky feature.
    support_tickets = rng.poisson(2.4, size=total).astype(float)

    churned = (
        (
            -0.040 * tenure_months
            + 0.014 * (60.0 - monthly_spend)
            + 0.62 * support_tickets
            + rng.normal(0.0, 0.45, size=total)
        )
        > 0.0
    ).astype(int)

    # Plan changes before the decision: near-noise, unrelated to churn.
    plan_changes_before = rng.poisson(0.45, size=total).astype(float)

    # Per-row cutoffs, the shape real decision tables have.
    offsets = rng.integers(0, 14 * 24, size=total)

    decisions_path = OUT / "retention_decisions.csv"
    with decisions_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "subscriber_key",
                "decided_at",
                "churned_within_90d",
                "eval_split",
                "tenure_months",
                "monthly_spend_usd",
                "support_tickets_90d",
            ]
        )
        for index in range(total):
            decided_at = DECISION_DAY + timedelta(hours=int(offsets[index]))
            writer.writerow(
                [
                    f"SUB-{index:05d}",
                    decided_at.isoformat() + "Z",
                    int(churned[index]),
                    "train" if index < TRAIN_ROWS else "test",
                    int(tenure_months[index]),
                    f"{monthly_spend[index]:.2f}",
                    int(support_tickets[index]),
                ]
            )

    # One row per observation of the running plan-change count, each stamped with
    # when it was recorded. The post-decision row is the defect: a churner
    # downgrades or cancels, so the count jumps only for them, and only after the
    # decision has already been made.
    history_path = OUT / "plan_change_history.csv"
    with history_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["subscriber", "recorded_at", "plan_changes_to_date"])
        for index in range(total):
            decided_at = DECISION_DAY + timedelta(hours=int(offsets[index]))

            writer.writerow(
                [
                    f"SUB-{index:05d}",
                    (decided_at - timedelta(days=45)).isoformat() + "Z",
                    int(max(0.0, plan_changes_before[index] - 1)),
                ]
            )
            writer.writerow(
                [
                    f"SUB-{index:05d}",
                    (decided_at - timedelta(days=3)).isoformat() + "Z",
                    int(plan_changes_before[index]),
                ]
            )

            cancelling = int(rng.poisson(2.9)) + 1 if churned[index] else int(rng.poisson(0.08))
            if cancelling:
                writer.writerow(
                    [
                        f"SUB-{index:05d}",
                        (decided_at + timedelta(days=int(rng.integers(2, 27)))).isoformat() + "Z",
                        int(plan_changes_before[index] + cancelling),
                    ]
                )

    print(f"wrote examples/adapter/{decisions_path.name}  ({total} rows)")
    print(f"wrote examples/adapter/{history_path.name}")
    print(f"churn rate {float(churned.mean()):.3f}  train {TRAIN_ROWS}  test {TEST_ROWS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
