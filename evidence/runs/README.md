# Local audit history

The evidence console writes one compact JSON summary here whenever an audit runs. These files are local product state, so `*.json` in this directory is intentionally ignored rather than committed.

Curated, reproducible evidence remains versioned in:

- `evidence/live/` — sanitized live DataHub and MCP proof;
- `evidence/phase0/` — feasibility and round-trip findings;
- `evidence/fixtures/` — recorded-fixture integrity evidence;
- `evaluations/` — frozen numerical results.

Deleting local run JSON only clears the console's history view; it does not remove any curated evidence or modify DataHub.
