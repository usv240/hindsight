# Audit configs

An audit config tells Hindsight what data to reconstruct, which SQL built the
feature, and which catalog asset the evidence describes.

```powershell
uv run hindsight demo-audit --audit audits/credit_default.json
uv run hindsight publish-audit --audit audits/my_pipeline.json
uv run hindsight serve --audit audits/my_pipeline.json --target-urn "<exact-dataset-urn>"
```

The console also reads `HINDSIGHT_AUDIT`.

## Audit fields

| Key | Required | Meaning |
|---|---:|---|
| `name` | no | Output label; defaults to the filename. |
| `scenario` | yes | Scenario policy plus generated or external point-in-time inputs. |
| `transformation_sql` | yes | Suspect transformation, parsed for an availability cutoff. |
| `remediation_sql` | yes | Proposed repair, verified independently. |
| `post_outcome_table` | yes | Relation whose rows exist only after prediction. |
| `available_column` | no | Availability-time column; default `available_at`. |
| `prediction_column` | no | Decision-time column; default `prediction_time`. |
| `target_urn` | no | Exact DataHub asset the evidence describes. Set this for write-back. |
| `synthetic` | no | Whether the input is synthetic; default `true`. |

## Exact target binding

An unbound audit may be evaluated and previewed, but it cannot perform approved
write-back. Bind the exact asset in JSON, set `HINDSIGHT_TARGET_URN`, or pass
`--target-urn` to `hindsight serve`. The console refuses every other target.
The CLI has a conspicuous `--allow-urn-mismatch` emergency override and records
its use; do not use it in normal operation.

## Point-in-time reconstruction on your files

A scenario can keep the frozen generator or map arbitrary CSV/Parquet column
names into Hindsight's canonical reconstruction contract. Use two relations:

- `applications`: one row per decision, with a unique entity ID, decision time,
  binary label, explicit `train`/`test` split, one or more numeric base`r`n  features, and a safe-control feature.
- `feature_records`: long-form history with entity ID, availability time, and the
  suspect feature value. Each decision needs at least one record available by
  its decision time.

Add this object to the scenario JSON:

```json
{
  "train_rows": 160,
  "test_rows": 40,
  "point_in_time_adapter": {
    "kind": "files",
    "applications": {"path": "decisions.parquet", "format": "parquet"},
    "feature_records": {"path": "feature_history.csv", "format": "csv"},
    "columns": {
      "entity_id": "loan key",
      "prediction_time": "decision timestamp",
      "label": "did default",
      "split": "evaluation split",
      "base_features": ["debt ratio", "account tenure"],
      "safe_feature": "prior missed payments",
      "record_entity_id": "record loan",
      "available_time": "recorded timestamp",
      "feature_value": "days since payment"
    }
  }
}
```

Paths are relative to the scenario file unless absolute. Run:

```powershell
uv run hindsight validate-point-in-time --scenario path/to/scenario.json
```

DuckDB maps the user-defined columns, selects the latest observed record and the
latest record available at decision time, and counts excluded post-cutoff
records. Hindsight fails closed on row-count or declared split mismatch,`r`nduplicate decision IDs,
null or unparseable required/base values, non-binary outcomes, malformed
history, or a decision with no pre-cutoff record. The report records the full
column mapping plus SHA-256 and byte size for both source files.

Current honest boundary: the adapter reads local CSV/Parquet snapshots; it does
not yet issue direct queries against arbitrary warehouse engines. Exported
relations are real external inputs, not the seeded generator, and their hashes
make the run reproducible.

For SQL-only temporal checks, no data adapter is required:

```powershell
uv run hindsight verify-sql path/to/feature.sql --post-outcome-table events_after_decision
```
