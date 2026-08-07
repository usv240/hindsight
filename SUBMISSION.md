# Devpost submission

Everything the submission form asks for, ready to paste. Kept in the repo so the
claims here and the code stay in sync.

---

## Project name

**Hindsight**

## Tagline (max ~200 chars)

> Models that score perfectly are often just cheating. Hindsight uses DataHub column lineage to prove whether a feature knew the answer before the decision was made — and blocks the release.

## Challenge track

**Production ML Agents** (also demonstrates Agents That Do Real Work)

## Built with

`python` · `datahub` · `mcp` · `duckdb` · `sqlglot` · `scikit-learn` · `fastapi` · `jinja` · `htmx` · `numpy` · `pytest` · `github-actions`

---

## Inspiration

A credit model scores beautifully in testing. It ships. It fails.

The model was never good — one of its features quietly contained the answer, built from events that only exist *after* the decision it was supposed to predict. This is **target leakage**, and it is one of the most expensive silent failures in production ML. Kapoor & Narayanan found it has corrupted **294 papers across 17 scientific disciplines**; Yang et al. found it **pervasive across 100,000+ public notebooks**.

What makes it so hard to catch is that it is a **cross-system, column-level** defect:

- the training notebook cannot see it — the leak happened upstream in the warehouse
- the feature store sees features, not their ancestry
- model monitoring fires months later, after the money is gone

DataHub's own blog states the thesis exactly: *"Without column-level lineage, these mistakes stay hidden until the model reaches production."* They published the argument and never built the tool. So we did.

## What it does

Hindsight is a **pre-release gate**. Given a model, it:

1. **Reads the ancestry** — walks DataHub's column-level lineage backwards from the model to find where each feature's information actually originated.
2. **Checks the clock** — compares when that information became available against the prediction cutoff, and parses the transformation SQL with `sqlglot` looking for an availability guard.
3. **Proves the consequence** — rebuilds the feature point-in-time in DuckDB, retrains, and measures how much of the model's advantage survives. Real skill persists. Borrowed hindsight collapses.
4. **Writes it back** — on explicit human approval, publishes a field tag, a structured verdict property, a linked audit Document and an active incident into DataHub, then **re-reads every one** to prove it persisted.
5. **Returns a CI exit code** so a pull request can be blocked automatically.

Three domains ship, each a real audit against its own synthetic data: **loan approval**, **hospital readmission**, and **fraud screening**.

## The result that proves it isn't theatre

| Feature | Ablation delta | Hindsight verdict |
|---|---:|---|
| Planted leaked feature | 0.21 | `confirmed` |
| Legitimate control | **0.24** | `clear_for_release` |

The **safe** feature matters more by ablation, and Hindsight clears it anyway.

That is the whole argument. Feature importance tells you a feature is *useful*; it says nothing about whether the information was **allowed to exist yet**. A detector built on ablation flags exactly the wrong feature here — which is why that control is a permanent regression test, not a demo prop.

## How we built it

A deterministic evidence engine with an LLM strictly outside the decision path. **An LLM may explain evidence; it can never promote a verdict.**

Verdicts are calibrated — `insufficient_metadata` → `needs_review` → `high_confidence` → `confirmed` — and `confirmed` is reachable by two independent routes:

- **a deterministic SQL/time proof** (the transformation joins a post-outcome source with no availability guard), or
- **a point-in-time collapse** (the advantage vanishes once the future is removed).

Each is sufficient alone, and the console names which one fired rather than blending them.

DataHub is reached through the **official MCP server** for discovery, lineage and governed mutations, and the **Python SDK** for typed ML metadata and write-back.

## Challenges

**Ablation cannot confirm leakage.** Our first verdict model let a plain ablation delta reach `confirmed`. But removing *any* strong feature drops accuracy — ablation measures importance, not admissibility. We rebuilt the lattice so ablation is structurally unreachable as a confirmation branch, and added a high-correlation control that must stay clear on every run.

**An evidence graphic that lied.** The cutoff timeline drew the decision line at 58% for composition while the axis computed it at 52.9% from real dates. On a graphic whose entire job is being trusted about time, that is fatal. A geometry test caught it; the window is now symmetric so one linear scale puts the cutoff exactly where it is drawn.

**A status light that always said "connected."** The console asserted a healthy DataHub connection whether or not one existed. It now probes, and reports `connected` / `degraded` / `offline` / `not configured` — and disables publishing when the catalog cannot be written.

**Writing evidence onto the wrong asset.** `publish-audit --target-urn` would happily tag *any* asset with this audit's verdict. Audits now name the asset they describe and **fail closed** on a mismatch.

## Accomplishments

- Two independent confirmation routes, with the fired route reported.
- A false-positive control with a *larger* ablation delta that must clear every run.
- Frozen generator, published threshold margin (5.142pp), and an honest disclosure that the planted leak is total by construction.
- Every catalog write re-read to prove persistence; dry-run by default.
- **215 tests**, CI on Ubuntu + Windows × Python 3.11 + 3.12, plus guards that fail the build on non-ASCII console output or a BOM in any JSON deliverable.
- Offline fixture replay so a reviewer sees it work in seconds with no Docker.

## What we learned

Being trusted matters more than being impressive. Almost every hard decision came down to refusing to overstate: not tuning the generator to produce a better number, publishing the threshold margin instead of hiding it, keeping `insufficient_metadata` as a real answer, and telling a reviewer plainly which parts do not yet work on their own data.

## What's next

- Point-in-time reconstruction against arbitrary warehouse schemas (CSV/Parquet snapshots can now be mapped onto arbitrary source columns; direct warehouse adapters remain future work).
- The remaining analyzers: training/serving skew and degenerate feedback loops.

---

## Testing instructions for judges

**Fastest path — no Docker, no DataHub, no API key, under a minute:**

```bash
git clone https://github.com/usv240/hindsight && cd hindsight
uv sync --extra dev
uv run hindsight demo
```

Prints the column lineage path, the 0.21-vs-0.24 contrast, and the point-in-time proof.

**The console:**

```bash
uv run hindsight serve      # http://127.0.0.1:8100
```

**Full live path** — local DataHub Core, MCP server, and approved write-back: see `QUICKSTART.md`.

## Links

- **Live demo:** https://hindsight-production-dd6e.up.railway.app - read-only, five real audits, nothing to install
- **Repository:** https://github.com/usv240/hindsight
- **Open-source contributions:**
  - [datahub#18705](https://github.com/datahub-project/datahub/pull/18705) — **merged** — documents the required `customType` field on `CUSTOM` incidents, which the tutorial omitted. Hit while building Hindsight's incident write-back; following the guide as written returns `customType is required: Failed to create incident.`
  - [datahub-skills#68](https://github.com/datahub-project/datahub-skills/pull/68) — open, awaiting review — adds the `datahub-ml-release-audit` skill.
- **Demo video:** _paste URL here_

## Feedback survey

Opt in. Feedback to give: fine-grained lineage emission needs a worked end-to-end example in the docs; the Analytics Agent quickstart is bash-only and needs a documented Windows/WSL2 path.
