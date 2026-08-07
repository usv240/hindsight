# Devpost "Additional info" step

Judges-only fields, plus the Feedback Prize answers. Every claim here is checked against the
repo.

## Challenge category

**Production ML Agents.**

It uses DataHub's end-to-end ML lineage through the Agent Context Kit to catch a silent
problem before it costs money, which is that category almost word for word. It also satisfies
"Agents That Do Real Work", but the form takes one, so take this one.

## Repository URL

```
https://github.com/usv240/hindsight
```

The Apache 2.0 licence file is present and GitHub detects it, so the badge appears in the
About panel. **The repo has to be public before you submit.**

## URL for judges to test the functionality

```
https://hindsight-production-dd6e.up.railway.app
```

## Link to generated artifacts

```
https://github.com/usv240/hindsight/tree/main/examples
```

That folder holds the audit document Hindsight publishes into DataHub, the leaky and
remediated SQL for two domains, machine-readable case files, a CI wiring example, and
`adapter/`, the external churn dataset with its CSVs committed.

## Which DataHub technologies did you use

Tick four, add one under Other, and leave one alone.

| Option | Tick? | What to say |
|---|:--:|---|
| DataHub OSS / Core Platform | **yes** | Core v1.5.0.6. Context graph, column-level lineage, ML entities, schema, profiles |
| DataHub MCP Server | **yes** | mcp-server-datahub 0.6.0. Discovery, lineage reads, governed mutations |
| DataHub Agent Context Kit | **yes** | `get_lineage_paths_between`, the directional column-level query the project rests on |
| DataHub Skills | **yes** | `datahub-ml-release-audit`, vendored in `skills/` and submitted upstream as datahub-skills#68 |
| Analytics Agent | **no** | Do not tick it. This is not a text-to-SQL product, and it would be the one unearned box on the form |
| Other | **yes** | DataHub Actions. An isolated deployment on the official Actions image audits a model the moment it appears, with nobody triggering it. See `docker/ACTION.md` |

## Did you contribute to DataHub during the hackathon

Yes, three. All of them came out of building this rather than out of looking for something to
contribute.

- https://github.com/datahub-project/datahub/pull/18705 (**merged**). The incidents tutorial
  lists `CUSTOM` as a supported type without mentioning that `customType` is required
  alongside it, so following the guide as written fails with
  `customType is required: Failed to create incident.`
- https://github.com/datahub-project/datahub/pull/18822 (open). `datahub docker quickstart`
  raises `UnicodeEncodeError` on Windows consoles using a legacy code page, after the stack is
  already healthy, so a successful install reports failure. The two worst call sites are the
  migration and repair instructions, which crash while explaining how to recover from a broken
  install.
- https://github.com/datahub-project/datahub-skills/pull/68 (open). Adds the
  `datahub-ml-release-audit` skill: verdict lattice, workflow, and an evidence validator.

## Country of residence

Yours to fill in. I have not guessed it.

## Newly created during the Submission Period

**Yes.** Verified from git history: first commit 2026-07-27, most recent 2026-08-07, both
inside the 6 July to 10 August window.

## Pre-existing code disclosure

Nothing beyond the standard tools the form already permits. Dependencies are ordinary
open-source libraries declared in `pyproject.toml` (FastAPI, Jinja, DuckDB, sqlglot,
scikit-learn, uvicorn) plus DataHub's own SDK, MCP server and Agent Context Kit. No starter
template. AI coding assistance was used, which the rules allow explicitly.

---

# Feedback Prize answers

Answer **yes** to the prize question, then paste these. Each one is something that actually
happened during this build.

## Which parts of DataHub felt polished or useful

**Column-level lineage with query entities is what made this project possible.**
`get_lineage_paths_between` through the Agent Context Kit returns not just that two columns
are connected, but the query entity sitting between them. That means our evidence chain cites
the catalog's own record of the transformation instead of a file we pointed the tool at.
Nothing else we looked at exposes that.

**The MCP Server's tool annotations are exactly right.** `readOnlyHint` and `destructiveHint`
let us build a human approval boundary that is honest about which calls mutate the catalog,
without maintaining our own hand-written list of which tools are safe.

**`datahub docker quickstart` really is one command.** Coming from tools that need a page of
setup, a single command that brings up a working catalog with sample data is a genuine
strength, and it is why our offline fixtures could be recorded from a real instance rather
than invented.

## Where did you get stuck or lose time

**Emitting fine-grained lineage is much harder than reading it.** The read path is documented
and pleasant. Producing `fineGrainedLineages` ourselves, which we needed in order to seed
realistic column-level fixtures, meant reading the Python SDK source. One worked end-to-end
example (here is a dataset with two columns, here is a query entity linking them, here is the
exact payload) would have saved most of a day.

**Incident creation fails on the documented example.** The tutorial lists `CUSTOM` as a type
but omits that `customType` is mandatory with it. We found the answer by reading the GraphQL
schema. Fixed in #18705.

**Quickstart crashes on Windows after succeeding.** The stack came up healthy and the CLI then
died printing a check mark to a cp1252 console. It looks like a broken install when it is a
working one. Fixed in #18822.

**Python version support is stated inconsistently** across different sources for the Actions
framework, which cost time before we settled on a version.

## If you had unlimited engineering time on DataHub, what would you build or fix first

**A first-class availability timestamp on datasets and columns.**

Every temporal correctness question reduces to "when did this row become knowable?", and
DataHub does not model that today. Lineage can say a column came from a table. It cannot say
that the rows in that table only appear three days after the event they describe.

We had to carry that fact in our own scenario config, which means the honest answer to "will
this work on your catalog?" is "only if you tell us separately". That is the single biggest
limit on this project, and it is not something we can fix from outside.

If availability semantics were part of the metadata model, an entire class of ML defect
(target leakage, training and serving skew, point-in-time correctness) would become answerable
directly from the catalog by any tool, not just ours. For teams shipping models on warehouse
data, that is the difference between catching leakage before release and finding it in the
loss numbers months later.

## Any bugs, errors, or unexpected behaviour

**1. UnicodeEncodeError in `datahub docker quickstart` on Windows.**

- Did: ran `datahub docker quickstart` in a standard Windows terminal (cp1252 code page),
  CLI 1.6.0.6, Core v1.5.0.6.
- Expected: the success message.
- Got: the stack came up healthy, then the CLI exited non-zero with
  `UnicodeEncodeError: charmap codec cannot encode character U+2714 in position 0`, raised
  from `docker_cli.py` while printing the check mark.
- Patch submitted as #18822.

**2. Incident creation rejects the documented CUSTOM example.**

- Did: followed the incidents tutorial to raise a `CUSTOM` incident.
- Expected: an incident.
- Got: `customType is required: Failed to create incident.` The required field is not
  mentioned on that page.
- Docs fix merged as #18705.

**3. Analytics Agent quickstart is bash-only.**

`quickstart.sh` assumes a POSIX shell. Windows users need WSL2 and the docs do not say so. A
one-line note would prevent a failed first run.
