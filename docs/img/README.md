# Screenshot capture checklist

Most judges will not stand up Docker and DataHub to evaluate a submission. These
screenshots are how a judge sees that Hindsight genuinely writes evidence back
into the catalog, which is the part of the rubric that rewards contributing to
the graph rather than only reading it.

Capture these while the live stack is running (`docker` + `hindsight serve`),
save them here with the exact filenames below, then uncomment the gallery in the
main `README.md`.

## Prerequisites

```powershell
# 1. DataHub Core running
#    http://localhost:9002   (datahub / datahub)
# 2. A published audit, so there is evidence to look at:
uv run hindsight publish-audit --target-urn "<synthetic-dataset-urn>" --approve-writeback
```

The synthetic dataset used for the recorded live proof was:

```text
urn:li:dataset:(urn:li:dataPlatform:duckdb,hindsight.phase0.leaky_features_1785182428,PROD)
```

Search for `hindsight` in the DataHub UI to find the current one.

## Required shots

| # | Filename | What must be visible | Why it matters |
|---|---|---|---|
| 1 | `datahub-column-lineage.png` | The column-level lineage view showing `payment_recorded_at` -> `days_since_last_payment` | This is the evidence the verdict rests on. It is the single most important image. |
| 2 | `datahub-field-tag.png` | The `hindsight:leakage-confirmed` tag on the offending schema field | Proves a write-back landed at column granularity |
| 3 | `datahub-structured-property.png` | The `hindsight.auditVerdict` structured property with its value | Proves typed, queryable metadata, not just a label |
| 4 | `datahub-incident.png` | The active `ML_LEAKAGE` incident on the model | Proves governed, actionable state in the catalog |
| 5 | `datahub-audit-document.png` | The linked audit Document with the evidence path | Proves durable institutional knowledge for the next human or agent |
| 6 | `hindsight-console.png` | `http://127.0.0.1:8100` showing the 0.21 vs 0.24 contrast and `awaiting_human_approval` | Shows the approval gate is real, not implied |

## Capture settings

- Viewport **1440x900** or wider, so the lineage graph is legible when scaled down.
- Light theme - it survives compression and projector rendering better than dark.
- Crop browser chrome, but keep the DataHub URL bar visible on shots 1-5. It is
  cheap proof the screenshot came from a real instance rather than a mockup.
- PNG, not JPEG. Text artifacts badly under JPEG compression.

## Gallery markup

Once the files exist, paste this into `README.md` under
"What Hindsight writes back to DataHub":

```markdown
| Column lineage in DataHub | Confirmed tag on the field |
|---|---|
| ![Column lineage](docs/img/datahub-column-lineage.png) | ![Field tag](docs/img/datahub-field-tag.png) |

| Structured verdict property | Active leakage incident |
|---|---|
| ![Structured property](docs/img/datahub-structured-property.png) | ![Incident](docs/img/datahub-incident.png) |
```
