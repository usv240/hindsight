# Hindsight

> Your model is not smarter. It has hindsight.

Hindsight is an evidence-based ML release gate that uses DataHub lineage and time semantics to catch target and temporal leakage before a model is promoted. Its deterministic core decides verdicts; an LLM may explain evidence, but cannot promote a verdict.

## Current status

The core Phase 0 feasibility gates pass. Hindsight now has a deterministic verdict engine, live DataHub lineage/write-back proof, official MCP read/mutation proof, bounded DuckDB point-in-time reconstruction, and a server-rendered evidence console. The frozen credit scenario confirms the planted leak while clearing a legitimately predictive safe control.

## Quick start

```powershell
uv sync --extra dev
uv run hindsight serve
uv run hindsight replay-fixture
uv run hindsight preflight --output evidence/phase0/preflight.local.json
uv sync --extra dev
uv run hindsight serve
uv run hindsight replay-fixture --extra datahub
uv run python -m hindsight.phase0.datahub_probe
uv run python -m hindsight.phase0.writeback_probe
uv run python -m hindsight.phase0.mcp_probe
uv run hindsight validate-credit --output evaluations/results.local.json
uv run hindsight verify-sql examples/leaky_feature.sql --post-outcome-table payment_events_after_decision
uv run hindsight demo-audit --output evidence/demo-audit.local.json
uv run hindsight publish-audit --target-urn "<dataset-urn>"
uv run hindsight publish-audit --target-urn "<dataset-urn>" --approve-writeback
uv run hindsight audit-fixture examples/confirmed_leakage.case.json
uv run pytest
```

The audit command exits `0` only for `clear_for_release`, `2` for incomplete/review evidence, and `3` for a blocking leakage verdict.

Open `http://127.0.0.1:8100` after `hindsight serve`. The console and CLI consume the same deterministic bundle. See [QUICKSTART.md](QUICKSTART.md) for offline and full DataHub paths.

For the fastest judge path, `hindsight replay-fixture` verifies the committed recording and reproduces the leakage verdict, safe control, SQL finding, and remediation in 0.023 seconds without Docker, DataHub, an LLM, or network access. The fixture also passes a live semantic-equivalence check against local DataHub. See [fixtures/credit_default/README.md](fixtures/credit_default/README.md) and [evaluations/fixture_replay.json](evaluations/fixture_replay.json).

## Evidence contract

Hindsight distinguishes five states:

- `insufficient_metadata`: required lineage or time evidence is absent.
- `needs_review`: ancestry looks suspicious, but direction or time is unproven.
- `high_confidence`: an outcome-derived path and availability-time violation are established.
- `confirmed`: deterministic cutoff proof or point-in-time reconstruction confirms the violation.
- `clear_for_release`: the configured checks pass.

Feature ablation is recorded only as explanatory importance evidence. It cannot confirm leakage.

## Measured validation result

The frozen 4,000-row credit scenario completed in 0.159 seconds. Its planted leakage case fell from AUC 1.000000 to 0.833630 under point-in-time reconstruction and reached `confirmed`. A legitimate pre-cutoff control retained AUC 0.924842 and remained `clear_for_release` despite a 0.226554 ablation delta. See [evaluations/results.json](evaluations/results.json).

The SQL verifier parses transformations with `sqlglot`. It blocks the leaky example because no cutoff on the configured post-outcome source exists, while [examples/remediation.sql](examples/remediation.sql) clears with the exact `payment.available_at <= application.prediction_time` predicate.

`hindsight demo-audit` combines transformation verification, point-in-time reconstruction, deterministic verdicting, the safe control, and remediation verification into one evidence bundle. It returns blocking exit code `3` and leaves DataHub write-back at `awaiting_human_approval`. A judge-readable example is available at [examples/audit_document.md](examples/audit_document.md).

`hindsight publish-audit` is dry-run by default and does not contact DataHub. The explicit `--approve-writeback` flag publishes the confirmed field tag, structured verdict, linked audit Document, and active incident, then rereads all four. Repeating an approved publication reuses the existing case incident. See [evidence/writeback/2026-07-27.md](evidence/writeback/2026-07-27.md).

## DataHub integration target

The live gate uses DataHub Core plus the Python SDK/MCP server to add and retrieve column-level lineage, then write approved audit evidence back to the graph. The official SDK supports custom downstream-to-upstream column mappings and retrieving column-level lineage paths.

## License

Apache License 2.0. See [LICENSE](LICENSE).
