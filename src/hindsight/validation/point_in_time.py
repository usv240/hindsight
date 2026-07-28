from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from hindsight.engine import audit_case
from hindsight.models import AuditCase


@dataclass(frozen=True)
class Comparison:
    baseline_auc: float
    observed_auc: float
    point_in_time_auc: float
    observed_advantage: float
    point_in_time_advantage: float
    advantage_retained: float
    collapsed: bool


def run_credit_validation(config_path: Path) -> dict[str, Any]:
    """Run one frozen scenario through a real DuckDB cutoff reconstruction.

    The historical function name remains as a compatibility alias, but the
    evidence identities and lineage paths are supplied by each scenario. This
    prevents a fraud or healthcare audit from emitting credit-risk proof.
    """
    started = time.perf_counter()
    raw_config = config_path.read_bytes()
    config = json.loads(raw_config)
    generated = _generate(config)

    with duckdb.connect(":memory:") as connection:
        _load_tables(connection, generated)
        reconstructed = connection.execute(
            """
            SELECT
                a.application_id,
                arg_max(r.feature_value, r.available_at) AS observed_value,
                arg_max(r.feature_value, r.available_at)
                    FILTER (WHERE r.available_at <= a.prediction_time) AS point_in_time_value,
                count(*) FILTER (WHERE r.available_at > a.prediction_time) AS excluded_records
            FROM applications AS a
            JOIN feature_records AS r USING (application_id)
            GROUP BY a.application_id
            ORDER BY a.application_id
            """
        ).fetchall()

    observed = np.asarray([row[1] for row in reconstructed], dtype=float)
    point_in_time = np.asarray([row[2] for row in reconstructed], dtype=float)
    excluded_records = int(sum(row[3] for row in reconstructed))
    base = generated["base_features"]
    label = generated["label"]
    split = int(config["train_rows"])

    baseline_auc = _auc(base, label, split)
    observed_auc = _auc(np.column_stack((base, observed)), label, split)
    point_in_time_auc = _auc(np.column_stack((base, point_in_time)), label, split)
    leakage = _compare(
        baseline_auc,
        observed_auc,
        point_in_time_auc,
        min_advantage=float(config["collapse_rule"]["minimum_observed_advantage"]),
        max_retained=float(config["collapse_rule"]["maximum_advantage_retained"]),
    )

    safe_observed_auc = _auc(np.column_stack((base, generated["safe_feature"])), label, split)
    safe_point_in_time_auc = _auc(np.column_stack((base, generated["safe_feature"])), label, split)
    safe_control = _compare(
        baseline_auc,
        safe_observed_auc,
        safe_point_in_time_auc,
        min_advantage=float(config["collapse_rule"]["minimum_observed_advantage"]),
        max_retained=float(config["collapse_rule"]["maximum_advantage_retained"]),
    )

    checks = {
        "post_cutoff_records_were_excluded": excluded_records > 0,
        "leaked_feature_advantage_collapsed": leakage.collapsed,
        "safe_feature_has_large_ablation_delta": (
            safe_control.observed_advantage
            >= float(config["safe_control_rule"]["minimum_ablation_delta"])
        ),
        "safe_feature_advantage_persisted": not safe_control.collapsed,
        "safe_feature_is_point_in_time_stable": (
            abs(safe_control.observed_auc - safe_control.point_in_time_auc) < 1e-12
        ),
    }
    prediction_time = datetime.fromisoformat(config["prediction_time"].replace("Z", "+00:00"))
    evidence = _evidence_profile(config)
    leakage_verdict = audit_case(
        AuditCase(
            case_id=evidence["leakage_case_id"],
            model_urn=evidence["leakage_model_urn"],
            feature_urn=evidence["leakage_feature_urn"],
            lineage_path=tuple(evidence["leakage_lineage_path"]),
            source_kind="post_outcome",
            source_available_at=prediction_time
            + timedelta(days=float(evidence["leakage_available_offset_days"])),
            prediction_time=prediction_time,
            point_in_time_advantage_collapsed=leakage.collapsed,
            ablation_delta=leakage.observed_advantage,
        )
    )
    safe_verdict = audit_case(
        AuditCase(
            case_id=evidence["safe_case_id"],
            model_urn=evidence["safe_model_urn"],
            feature_urn=evidence["safe_feature_urn"],
            lineage_path=tuple(evidence["safe_lineage_path"]),
            source_kind="pre_outcome",
            source_available_at=prediction_time
            + timedelta(days=float(evidence["safe_available_offset_days"])),
            prediction_time=prediction_time,
            point_in_time_advantage_collapsed=safe_control.collapsed,
            ablation_delta=safe_control.observed_advantage,
        )
    )
    return {
        "schema_version": 1,
        "scenario": config["scenario"],
        "config_sha256": hashlib.sha256(raw_config).hexdigest(),
        "seed": config["seed"],
        "rows": config["train_rows"] + config["test_rows"],
        "runtime_seconds": round(time.perf_counter() - started, 6),
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "reconstruction": {
            "engine": "duckdb",
            "cutoff_predicate": "available_at <= prediction_time",
            "excluded_post_cutoff_records": excluded_records,
        },
        "evidence_context": evidence,
        "leakage_case": asdict(leakage),
        "safe_control": asdict(safe_control),
        "verdicts": {
            "leakage_case": leakage_verdict.to_dict(),
            "safe_control": safe_verdict.to_dict(),
        },
    }


def _evidence_profile(config: dict[str, Any]) -> dict[str, Any]:
    """Return scenario-specific identities with legacy credit defaults."""

    defaults: dict[str, Any] = {
        "decision_node": "applications_at_decision_time.prediction_time",
        "leakage_case_id": "credit-default-leaked-payment-event",
        "safe_case_id": "credit-default-prior-delinquencies-safe-control",
        "leakage_model_urn": "urn:li:mlModel:hindsight.credit_default_v1_leaky",
        "safe_model_urn": "urn:li:mlModel:hindsight.credit_default_v2_safe",
        "leakage_feature_urn": (
            "urn:li:schemaField:(hindsight.feature_pipeline_leaky,days_since_last_payment)"
        ),
        "safe_feature_urn": (
            "urn:li:schemaField:(hindsight.customer_history_point_in_time,prior_delinquencies)"
        ),
        "leakage_lineage_path": [
            "payment_events_after_decision.payment_recorded_at",
            "feature_pipeline_leaky.days_since_last_payment",
        ],
        "safe_lineage_path": [
            "customer_history_point_in_time.prior_delinquencies",
            "feature_pipeline_safe.prior_delinquencies",
        ],
        "leakage_available_offset_days": 31,
        "safe_available_offset_days": -1,
    }
    supplied = config.get("audit_evidence", {})
    if not isinstance(supplied, dict):
        raise ValueError("audit_evidence must be a JSON object")
    profile = defaults | supplied
    for key in ("leakage_lineage_path", "safe_lineage_path"):
        path = profile.get(key)
        if (
            not isinstance(path, list)
            or len(path) < 2
            or not all(isinstance(node, str) and node for node in path)
        ):
            raise ValueError(f"audit_evidence.{key} must contain at least two nodes")
    profile["leakage_feature_name"] = profile["leakage_lineage_path"][-1].rsplit(".", 1)[-1]
    profile["safe_feature_name"] = profile["safe_lineage_path"][-1].rsplit(".", 1)[-1]
    return profile


def _generate(config: dict[str, Any]) -> dict[str, Any]:
    rng = np.random.default_rng(int(config["seed"]))
    rows = int(config["train_rows"]) + int(config["test_rows"])
    latent_risk = rng.normal(size=rows)
    prior_delinquencies = rng.poisson(np.exp(np.clip(0.55 * latent_risk, -1.2, 1.2)))
    debt_to_income = np.clip(rng.normal(0.38 + 0.07 * latent_risk, 0.12), 0.05, 0.95)
    monthly_income = np.exp(rng.normal(8.45 - 0.10 * latent_risk, 0.42))
    label_score = (
        1.35 * prior_delinquencies
        + 2.0 * debt_to_income
        + 0.35 * latent_risk
        + rng.normal(0, 1.15, rows)
    )
    label = (label_score >= np.quantile(label_score, 0.70)).astype(int)

    historical_days = np.clip(18 + 9 * prior_delinquencies + rng.normal(0, 10, rows), 0, None)
    post_outcome_days = np.where(
        label == 1,
        150 + rng.normal(0, 12, rows),
        4 + rng.normal(0, 2, rows),
    )
    return {
        "base_features": np.column_stack((debt_to_income, np.log1p(monthly_income))),
        "safe_feature": prior_delinquencies.astype(float),
        "historical_days": historical_days,
        "post_outcome_days": np.clip(post_outcome_days, 0, None),
        "label": label,
    }


def _load_tables(connection: duckdb.DuckDBPyConnection, data: dict[str, Any]) -> None:
    rows = len(data["label"])
    application_source = np.vstack((np.arange(rows), np.zeros(rows)))
    feature_source = np.vstack(
        (
            np.tile(np.arange(rows), 2),
            np.concatenate((np.full(rows, -1), np.full(rows, 31))),
            np.concatenate((data["historical_days"], data["post_outcome_days"])),
        )
    )
    connection.register("application_source", application_source)
    connection.register("feature_source", feature_source)
    connection.execute(
        """
        CREATE TABLE applications AS
        SELECT column0::INTEGER AS application_id,
               TIMESTAMP '2026-01-10 09:00:00'
                   + column1 * INTERVAL '1 day' AS prediction_time
        FROM application_source
        """
    )
    connection.execute(
        """
        CREATE TABLE feature_records AS
        SELECT column0::INTEGER AS application_id,
               TIMESTAMP '2026-01-10 09:00:00'
                   + column1 * INTERVAL '1 day' AS available_at,
               column2::DOUBLE AS feature_value
        FROM feature_source
        """
    )


def _auc(features: np.ndarray, labels: np.ndarray, split: int) -> float:
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=1.0, max_iter=500, random_state=0),
    )
    model.fit(features[:split], labels[:split])
    probabilities = model.predict_proba(features[split:])[:, 1]
    return round(float(roc_auc_score(labels[split:], probabilities)), 6)


def _compare(
    baseline_auc: float,
    observed_auc: float,
    point_in_time_auc: float,
    *,
    min_advantage: float,
    max_retained: float,
) -> Comparison:
    observed_advantage = round(observed_auc - baseline_auc, 6)
    point_in_time_advantage = round(point_in_time_auc - baseline_auc, 6)
    retained = point_in_time_advantage / observed_advantage if observed_advantage > 0 else 1.0
    return Comparison(
        baseline_auc=baseline_auc,
        observed_auc=observed_auc,
        point_in_time_auc=point_in_time_auc,
        observed_advantage=observed_advantage,
        point_in_time_advantage=point_in_time_advantage,
        advantage_retained=round(retained, 6),
        collapsed=observed_advantage >= min_advantage and retained <= max_retained,
    )
