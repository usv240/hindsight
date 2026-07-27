# Hindsight quickstart

## Evidence console without DataHub

From the `hindsight` directory:

```powershell
uv sync --extra dev
uv run hindsight serve
```

Open `http://127.0.0.1:8100`. The page executes the frozen scenario, SQL
verification, point-in-time reconstruction, deterministic verdict, safe
control, and remediation verification locally. No LLM or network call is
required.

Useful endpoints:

- `/` — server-rendered evidence console
- `/api/audit` — machine-readable audit bundle
- `/health` — process health

## Full DataHub path

Start the documented local DataHub quickstart and standalone MCP server, then:

```powershell
uv sync --extra dev --extra datahub
uv run python -m hindsight.phase0.datahub_probe
uv run python -m hindsight.phase0.mcp_probe
uv run hindsight serve
```

The console's publication form is dry-run by default. To publish, paste the
synthetic leaky dataset URN returned by the probe and explicitly select the
approval checkbox. The server writes the confirmed field tag, structured
property, linked audit Document, and active incident, then rereads all four.

Never enable approved mutation against a production catalog for the demo.

## CLI-only golden path

```powershell
uv run hindsight demo-audit --output evidence/demo-audit.local.json
```

Exit code `3` is expected: the release is correctly blocked. Raw `*.local.json`
reports are ignored by Git.

## Verification

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv build
```
