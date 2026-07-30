# Hindsight quickstart

Run commands from the `hindsight` directory.

## One-command judge path

```powershell
uv sync --extra dev
uv run hindsight demo
```

This is the command to run first. It shows the planted case, the safe control,
the `0.21` versus `0.24` ablation reversal, the independent point-in-time proof,
and the synthetic-demo disclosures. It uses no external service and returns `0`
when every expected outcome is reproduced.

For machine-readable output:

```powershell
uv run hindsight demo --json --output evaluations/demo.local.json
```

## Evidence console without DataHub

```powershell
uv run hindsight serve
```

Open `http://127.0.0.1:8100`. The page executes the frozen scenario, SQL
verification, point-in-time reconstruction, deterministic verdict, safe
control, and remediation verification locally. No LLM or network call is
required.

Useful endpoints:

- `/` - server-rendered evidence console
- `/api/audit` - machine-readable audit bundle
- `/health` - process health

## Full DataHub path

Start the documented local DataHub quickstart and standalone MCP server, then:

```powershell
uv sync --extra dev --extra datahub
uv run python -m hindsight.phase0.datahub_probe
$target = (Get-Content evidence/phase0/datahub-roundtrip.local.json | ConvertFrom-Json).entities.downstream
uv run python -m hindsight.phase0.mcp_probe
uv run hindsight verify-fixture-live --target-urn $target
uv run hindsight serve --target-urn $target
```

The console publication form is dry-run by default. `--target-urn` binds the evidence to
the exact synthetic dataset returned by the probe; the console refuses approved write-back
to any other asset. Explicitly select the approval checkbox to publish. The server writes the confirmed field tag, structured
property, linked audit Document, and active incident, then rereads all four.

Never enable approved mutation against a production catalog for the demo.

## External point-in-time data

Map arbitrary CSV or Parquet column names in a scenario's
`point_in_time_adapter`, then run:

```powershell
uv run hindsight validate-point-in-time --scenario path/to/scenario.json
```

The input contract and complete mapping example are in
[`audits/README.md`](audits/README.md). Reports include both input hashes and the
exact mapping used.

## Event-driven DataHub Action

The Action is isolated on DataHub's official compatible runtime. With the local
DataHub quickstart running, bind it to one exact model URN and follow
[`docker/ACTION.md`](docker/ACTION.md). It consumes model-property changes,
deduplicates exact event redeliveries, and emits a machine-readable local proof without
autonomously mutating governed metadata.
## CI release-gate path

```powershell
uv run hindsight demo-audit --output evidence/demo-audit.local.json
```

Exit code `3` is expected because this command models the release gate and the
candidate is correctly blocked. Raw `*.local.json` reports are ignored by Git.

## Verification

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv build
```
