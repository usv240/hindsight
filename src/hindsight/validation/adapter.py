"""Configurable point-in-time inputs for real pipeline data.

The frozen demo generator remains the default, but a scenario may instead name
an applications relation and a long-form feature-record relation. DuckDB maps
user-defined columns into the canonical reconstruction contract.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import numpy as np


class AdapterConfigError(ValueError):
    """The external point-in-time input contract is invalid."""


@dataclass(frozen=True)
class AdaptedInput:
    base_features: np.ndarray
    safe_feature: np.ndarray
    label: np.ndarray
    observed: np.ndarray
    point_in_time: np.ndarray
    excluded_records: int
    provenance: dict[str, Any]


def load_adapted_input(config: dict[str, Any], config_path: Path) -> AdaptedInput | None:
    """Load external CSV/Parquet relations, or return None for the generator."""
    adapter = config.get("point_in_time_adapter")
    if adapter is None:
        return None
    if not isinstance(adapter, dict):
        raise AdapterConfigError("point_in_time_adapter must be a JSON object")
    kind = adapter.get("kind")
    if kind not in {"files", "wide_snapshots"}:
        raise AdapterConfigError("point_in_time_adapter.kind must be 'files' or 'wide_snapshots'")
    wide = kind == "wide_snapshots"

    applications = _relation(adapter, "applications", config_path)
    records = _relation(adapter, "feature_snapshots" if wide else "feature_records", config_path)
    columns = adapter.get("columns")
    if not isinstance(columns, dict):
        raise AdapterConfigError("point_in_time_adapter.columns must be a JSON object")

    shared = (
        "entity_id",
        "prediction_time",
        "label",
        "split",
        "base_features",
        "safe_feature",
    )
    # A long-form history names the value column; a wide snapshot table names
    # which of its many feature columns is under audit.
    required = shared + (
        ("snapshot_entity_id", "snapshot_time", "feature")
        if wide
        else ("record_entity_id", "available_time", "feature_value")
    )
    missing = [key for key in required if not columns.get(key)]
    if missing:
        raise AdapterConfigError(f"point_in_time_adapter.columns is missing: {', '.join(missing)}")
    base_columns = columns["base_features"]
    if (
        not isinstance(base_columns, list)
        or not base_columns
        or not all(isinstance(item, str) and item.strip() for item in base_columns)
    ):
        raise AdapterConfigError("point_in_time_adapter.columns.base_features must be a list")

    with duckdb.connect(":memory:") as connection:
        _read_relation(connection, "raw_applications", applications)
        _read_relation(connection, "raw_feature_records", records)
        _materialize_applications(connection, columns, base_columns)
        if wide:
            _materialize_records_from_wide(connection, columns)
        else:
            _materialize_records(connection, columns)
        _validate_relations(
            connection,
            train_rows=int(config["train_rows"]),
            test_rows=int(config["test_rows"]),
            base_width=len(base_columns),
        )

        base_projection = ", ".join(f"base_{index}" for index in range(len(base_columns)))
        application_rows = connection.execute(
            f"""
            SELECT {base_projection}, safe_feature, label
            FROM applications
            ORDER BY row_order
            """
        ).fetchall()
        reconstructed = connection.execute(
            """
            SELECT
                a.row_order,
                arg_max(r.feature_value, r.available_at) AS observed_value,
                arg_max(r.feature_value, r.available_at)
                    FILTER (WHERE r.available_at <= a.prediction_time) AS point_in_time_value,
                count(*) FILTER (WHERE r.available_at > a.prediction_time) AS excluded_records
            FROM applications AS a
            JOIN feature_records AS r USING (entity_id)
            GROUP BY a.row_order
            ORDER BY a.row_order
            """
        ).fetchall()

    if len(reconstructed) != len(application_rows):
        raise AdapterConfigError("every application must have at least one feature record")
    if any(row[2] is None for row in reconstructed):
        raise AdapterConfigError(
            "every application needs a feature record available by prediction time"
        )

    width = len(base_columns)
    return AdaptedInput(
        base_features=np.asarray([row[:width] for row in application_rows], dtype=float),
        safe_feature=np.asarray([row[width] for row in application_rows], dtype=float),
        label=np.asarray([row[width + 1] for row in application_rows], dtype=int),
        observed=np.asarray([row[1] for row in reconstructed], dtype=float),
        point_in_time=np.asarray([row[2] for row in reconstructed], dtype=float),
        excluded_records=int(sum(row[3] for row in reconstructed)),
        provenance={
            "adapter": kind,
            "applications": _provenance(applications),
            ("feature_snapshots" if wide else "feature_records"): _provenance(records),
            "column_mapping": columns,
        },
    )


def _relation(adapter: dict[str, Any], key: str, config_path: Path) -> dict[str, Any]:
    value = adapter.get(key)
    if not isinstance(value, dict) or not isinstance(value.get("path"), str):
        raise AdapterConfigError(f"point_in_time_adapter.{key}.path is required")
    path = Path(value["path"])
    configured_path = value["path"].replace("\\", "/")
    if not path.is_absolute():
        path = config_path.parent / path
    path = path.resolve()
    if not path.is_file():
        raise AdapterConfigError(f"point_in_time_adapter.{key} not found: {path}")
    file_format = value.get("format", path.suffix.lstrip(".").lower())
    if file_format not in {"csv", "parquet"}:
        raise AdapterConfigError(f"point_in_time_adapter.{key}.format must be csv or parquet")
    display_path = (
        configured_path if not Path(value["path"]).is_absolute() else f"<external>/{path.name}"
    )
    return {"path": path, "display_path": display_path, "format": file_format}


def _read_relation(
    connection: duckdb.DuckDBPyConnection,
    view_name: str,
    relation: dict[str, Any],
) -> None:
    path = str(relation["path"])
    source = (
        connection.read_csv(path, header=True)
        if relation["format"] == "csv"
        else connection.read_parquet(path)
    )
    source.create_view(view_name)


def _materialize_applications(
    connection: duckdb.DuckDBPyConnection,
    columns: dict[str, Any],
    base_columns: list[str],
) -> None:
    bases = ",\n".join(
        f"TRY_CAST({_identifier(name)} AS DOUBLE) AS base_{index}"
        for index, name in enumerate(base_columns)
    )
    connection.execute(
        f"""
        CREATE TABLE applications AS
        SELECT
            row_number() OVER (
                ORDER BY
                    CASE lower(trim(CAST({_identifier(columns["split"])} AS VARCHAR)))
                        WHEN 'train' THEN 0 WHEN 'test' THEN 1 ELSE 2
                    END,
                    CAST({_identifier(columns["entity_id"])} AS VARCHAR)
            ) AS row_order,
            CAST({_identifier(columns["entity_id"])} AS VARCHAR) AS entity_id,
            TRY_CAST({_identifier(columns["prediction_time"])} AS TIMESTAMP) AS prediction_time,
            TRY_CAST({_identifier(columns["label"])} AS INTEGER) AS label,
            lower(trim(CAST({_identifier(columns["split"])} AS VARCHAR))) AS split_name,
            {bases},
            TRY_CAST({_identifier(columns["safe_feature"])} AS DOUBLE) AS safe_feature
        FROM raw_applications
        """
    )


def _materialize_records(
    connection: duckdb.DuckDBPyConnection,
    columns: dict[str, Any],
) -> None:
    connection.execute(
        f"""
        CREATE TABLE feature_records AS
        SELECT
            CAST({_identifier(columns["record_entity_id"])} AS VARCHAR) AS entity_id,
            TRY_CAST({_identifier(columns["available_time"])} AS TIMESTAMP) AS available_at,
            TRY_CAST({_identifier(columns["feature_value"])} AS DOUBLE) AS feature_value
        FROM raw_feature_records
        """
    )


def _materialize_records_from_wide(
    connection: duckdb.DuckDBPyConnection,
    columns: dict[str, Any],
) -> None:
    """Project one column of a wide snapshot table into the long-form contract.

    Most warehouses keep features wide - one row per entity per as-of date, with
    a column per feature - rather than as an event log. Selecting the audited
    column as the value reuses every downstream guard unchanged, so the wide path
    is a translation rather than a second implementation.
    """
    connection.execute(
        f"""
        CREATE TABLE feature_records AS
        SELECT
            CAST({_identifier(columns["snapshot_entity_id"])} AS VARCHAR) AS entity_id,
            TRY_CAST({_identifier(columns["snapshot_time"])} AS TIMESTAMP) AS available_at,
            TRY_CAST({_identifier(columns["feature"])} AS DOUBLE) AS feature_value
        FROM raw_feature_records
        """
    )


def _validate_relations(
    connection: duckdb.DuckDBPyConnection, *, train_rows: int, test_rows: int, base_width: int
) -> None:
    base_nulls = " OR ".join(f"base_{index} IS NULL" for index in range(base_width))
    expected_rows = train_rows + test_rows
    rows, unique_ids, invalid_rows, labels, actual_train, actual_test = connection.execute(
        f"""
        SELECT
            count(*),
            count(DISTINCT entity_id),
            count(*) FILTER (
                WHERE entity_id IS NULL OR prediction_time IS NULL OR label IS NULL
                   OR safe_feature IS NULL OR {base_nulls}
            ),
            count(DISTINCT label),
            count(*) FILTER (WHERE split_name = 'train'),
            count(*) FILTER (WHERE split_name = 'test')
        FROM applications
        """
    ).fetchone()
    if rows != expected_rows:
        raise AdapterConfigError(f"applications has {rows} rows; scenario declares {expected_rows}")
    if unique_ids != rows:
        raise AdapterConfigError("applications entity IDs must be unique")
    if invalid_rows:
        raise AdapterConfigError("applications contains null or unparseable required values")
    if labels != 2:
        raise AdapterConfigError("applications label must contain exactly two classes")
    if actual_train != train_rows or actual_test != test_rows:
        raise AdapterConfigError(
            "applications split counts do not match declared train_rows/test_rows"
        )
    invalid_records = connection.execute(
        """
        SELECT count(*) FROM feature_records
        WHERE entity_id IS NULL OR available_at IS NULL OR feature_value IS NULL
        """
    ).fetchone()[0]
    if invalid_records:
        raise AdapterConfigError("feature_records contains null or unparseable required values")
    ambiguous_records = connection.execute(
        """
        SELECT count(*) FROM (
            SELECT entity_id, available_at
            FROM feature_records
            GROUP BY entity_id, available_at
            HAVING min(feature_value) != max(feature_value)
        )
        """
    ).fetchone()[0]
    if ambiguous_records:
        raise AdapterConfigError(
            "feature_records has conflicting values at the same entity and timestamp"
        )


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AdapterConfigError("column mappings must be non-empty strings")
    return '"' + value.replace('"', '""') + '"'


def _provenance(relation: dict[str, Any]) -> dict[str, Any]:
    path: Path = relation["path"]
    return {
        "path": relation["display_path"],
        "format": relation["format"],
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bytes": path.stat().st_size,
    }
