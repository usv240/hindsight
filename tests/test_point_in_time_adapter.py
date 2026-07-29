from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from hindsight.validation.adapter import AdapterConfigError
from hindsight.validation.point_in_time import run_point_in_time_validation


def _write_external_scenario(
    root: Path,
    *,
    duplicate_id: bool = False,
    invalid_base: bool = False,
    invalid_split: bool = False,
    ambiguous_record: bool = False,
) -> Path:
    applications = root / "decisions.csv"
    records = root / "history.csv"
    with applications.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "loan key",
                "decision timestamp",
                "did default",
                "split",
                "ratio",
                "tenure",
                "prior misses",
            ]
        )
        for index in range(200):
            entity = "loan-0" if duplicate_id and index == 1 else f"loan-{index}"
            label = index % 2
            ratio = "" if invalid_base and index == 0 else index % 5
            split = (
                "invalid" if invalid_split and index == 0 else ("train" if index < 160 else "test")
            )
            writer.writerow(
                [
                    entity,
                    "2026-02-01T00:00:00Z",
                    label,
                    split,
                    ratio,
                    index % 7,
                    label * 10,
                ]
            )

    with records.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["record loan", "recorded timestamp", "days value"])
        for index in range(200):
            writer.writerow([f"loan-{index}", "2026-01-31T00:00:00Z", index % 3])
            writer.writerow([f"loan-{index}", "2026-02-02T00:00:00Z", (index % 2) * 20])
        if ambiguous_record:
            writer.writerow(["loan-0", "2026-01-31T00:00:00Z", 999])

    scenario = {
        "schema_version": 1,
        "scenario": "external_renamed_columns",
        "seed": 0,
        "train_rows": 160,
        "test_rows": 40,
        "prediction_time": "2026-02-01T00:00:00Z",
        "collapse_rule": {
            "minimum_observed_advantage": 0.05,
            "maximum_advantage_retained": 0.5,
        },
        "safe_control_rule": {"minimum_ablation_delta": 0.2},
        # An adapter scenario must declare its own identities: the credit-risk
        # defaults would otherwise be asserted over someone else's dataset.
        "audit_evidence": {
            "decision_node": "decisions.decision timestamp",
            "leakage_case_id": "external-renamed-leak",
            "safe_case_id": "external-renamed-safe-control",
            "leakage_model_urn": (
                "urn:li:mlModel:(urn:li:dataPlatform:mlflow,external.renamed_leaky,PROD)"
            ),
            "safe_model_urn": (
                "urn:li:mlModel:(urn:li:dataPlatform:mlflow,external.renamed_safe,PROD)"
            ),
            "leakage_feature_urn": "urn:li:schemaField:(external.features,days since payment)",
            "safe_feature_urn": "urn:li:schemaField:(external.features,prior misses)",
            "leakage_lineage_path": ["history.recorded timestamp", "features.days since payment"],
            "safe_lineage_path": ["decisions.prior misses", "features.prior misses"],
        },
        "point_in_time_adapter": {
            "kind": "files",
            "applications": {"path": "decisions.csv", "format": "csv"},
            "feature_records": {"path": "history.csv", "format": "csv"},
            "columns": {
                "entity_id": "loan key",
                "prediction_time": "decision timestamp",
                "label": "did default",
                "split": "split",
                "base_features": ["ratio", "tenure"],
                "safe_feature": "prior misses",
                "record_entity_id": "record loan",
                "available_time": "recorded timestamp",
                "feature_value": "days value",
            },
        },
    }
    path = root / "scenario.json"
    path.write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8")
    return path


def test_file_adapter_reconstructs_external_columns_and_hashes_inputs(tmp_path: Path) -> None:
    report = run_point_in_time_validation(_write_external_scenario(tmp_path))

    assert report["status"] == "passed"
    assert report["reconstruction"]["input"]["adapter"] == "files"
    assert report["reconstruction"]["excluded_post_cutoff_records"] == 200
    assert report["leakage_case"]["collapsed"] is True
    assert report["safe_control"]["collapsed"] is False
    assert report["verdicts"]["leakage_case"]["verdict"] == "confirmed"
    assert len(report["reconstruction"]["input"]["applications"]["sha256"]) == 64
    assert report["reconstruction"]["input"]["applications"]["path"] == "decisions.csv"
    assert report["reconstruction"]["input"]["column_mapping"]["entity_id"] == "loan key"


def test_file_adapter_rejects_duplicate_application_ids(tmp_path: Path) -> None:
    path = _write_external_scenario(tmp_path, duplicate_id=True)
    with pytest.raises(AdapterConfigError, match="entity IDs must be unique"):
        run_point_in_time_validation(path)


def test_file_adapter_rejects_unparseable_base_features(tmp_path: Path) -> None:
    path = _write_external_scenario(tmp_path, invalid_base=True)
    with pytest.raises(AdapterConfigError, match="null or unparseable required values"):
        run_point_in_time_validation(path)


def test_file_adapter_requires_declared_split_counts(tmp_path: Path) -> None:
    path = _write_external_scenario(tmp_path, invalid_split=True)
    with pytest.raises(AdapterConfigError, match="split counts"):
        run_point_in_time_validation(path)


def test_file_adapter_rejects_ambiguous_same_time_values(tmp_path: Path) -> None:
    path = _write_external_scenario(tmp_path, ambiguous_record=True)
    with pytest.raises(AdapterConfigError, match="conflicting values"):
        run_point_in_time_validation(path)


def test_cli_reports_invalid_mapping_without_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from hindsight.cli import main

    scenario = _write_external_scenario(tmp_path)
    payload = json.loads(scenario.read_text(encoding="utf-8"))
    del payload["point_in_time_adapter"]["columns"]["split"]
    scenario.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "report.json"

    assert (
        main(["validate-point-in-time", "--scenario", str(scenario), "--output", str(output)]) == 2
    )
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "invalid_input"
    assert "columns is missing: split" in report["error"]
    assert json.loads(output.read_text(encoding="utf-8")) == report
