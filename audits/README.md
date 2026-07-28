# Audit configs

An audit config tells Hindsight three things: **what data to reconstruct**, **which SQL
built the feature**, and **which catalog asset the resulting evidence is about**.

Pass one with `--audit`:

```powershell
uv run hindsight demo-audit --audit audits/credit_default.json
uv run hindsight publish-audit --audit audits/my_pipeline.json
uv run hindsight serve --audit audits/my_pipeline.json --target-urn "<exact-dataset-urn>"
```

The console also reads `HINDSIGHT_AUDIT`.

## Fields

| Key | Required | Meaning |
|---|---|---|
| `name` | no | Label used in output. Defaults to the filename. |
| `scenario` | **yes** | Path to the scenario data config used for point-in-time reconstruction. |
| `transformation_sql` | **yes** | The SQL that builds the suspect feature. Parsed for an availability cutoff. |
| `remediation_sql` | **yes** | The proposed repair, verified independently. |
| `post_outcome_table` | **yes** | The table whose rows only exist after the prediction cutoff. |
| `available_column` | no | Column carrying availability time. Default `available_at`. |
| `prediction_column` | no | Column carrying the prediction cutoff. Default `prediction_time`. |
| `target_urn` | no | The DataHub asset this evidence describes. **Set this.** See below. |
| `synthetic` | no | Whether the underlying data is synthetic. Default `true`. |

## Why `target_urn` matters

An unbound audit may be evaluated and previewed, but it cannot perform approved write-back.
Bind the exact asset in the JSON config, set `HINDSIGHT_TARGET_URN`, or pass
`--target-urn` to `hindsight serve`. The web console then refuses every other target.

The CLI exposes `--allow-urn-mismatch` as a conspicuous emergency override for approved
automation. Hindsight records use of that override. Do not use it for the demo or normal operation:
writing a correct verdict onto the wrong asset creates false catalog evidence.

## Pointing this at your own pipeline

Current honest status: the reconstruction engine expects the scenario-data shape used by
the seeded scenario, so adapting it to your warehouse means producing a scenario config
that the validation runner can load. The SQL verification, verdict lattice, approval gate
and DataHub write-back are already generic and work against any asset.

If you only want the SQL and lineage checks against your own transformation, `verify-sql`
runs standalone today:

```powershell
uv run hindsight verify-sql path/to/your_feature.sql --post-outcome-table your_events_table
```
