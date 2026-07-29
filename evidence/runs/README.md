# Local audit history

The evidence console writes one compact JSON summary here whenever an audit runs. These files are local product state, so `*.json` in this directory is intentionally ignored rather than committed.

## Except five

Five are tracked, one per scenario, force-added past that ignore rule. Without them a fresh clone opens the console on an empty page, and the hosted read-only demo has nothing to serve. They are unmodified output from real runs, not fixtures written by hand:

| Scenario | Decision | Verdict |
| --- | --- | --- |
| `credit_default` | block | confirmed |
| `credit_default_subtle` | block | confirmed |
| `credit_default_fixed` | allow | clear_for_release |
| `fraud_screening` | block | confirmed |
| `hospital_readmission` | block | confirmed |

Running your own audits adds files alongside them and never overwrites them, because run ids are timestamped.

Curated, reproducible evidence remains versioned in:

- `evidence/live/` — sanitized live DataHub and MCP proof;
- `evidence/phase0/` — feasibility and round-trip findings;
- `evidence/fixtures/` — recorded-fixture integrity evidence;
- `evaluations/` — frozen numerical results.

Deleting local run JSON only clears the console's history view; it does not remove any curated evidence or modify DataHub.
