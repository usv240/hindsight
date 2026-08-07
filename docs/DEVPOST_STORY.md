## Inspiration

A bank builds a model to predict who will repay a loan. It scores almost perfectly in
testing. They ship it. It fails.

The model was never good. One of the facts it was shown could only be known **after** the
loan decision had already been made, so in testing it was reading the answer, and in
production that answer does not exist yet. This is **target leakage**.

It is not a rare curiosity. Kapoor & Narayanan traced it through **294 papers across 17
scientific disciplines** (*Leakage and the Reproducibility Crisis in ML-based Science*,
Patterns 2023). Yang, Brower-Sinning, Lewis & Kästner found it **pervasive across 100,000+
public notebooks** ([arXiv:2209.03345](https://arxiv.org/abs/2209.03345), ASE 2022). Kaufman,
Rosset & Perlich gave it its formal definition back at **KDD 2011**.

What makes it hard to catch is *where* it happens. The mistake is not in the notebook. It is
upstream, in a data pipeline nobody on the ML team ever opens:

- the training notebook cannot see it, the defect was created before `read_parquet`
- the feature store sees finished features, not where they came from
- monitoring notices months later, once the losses arrive
- a data quality tool finds nothing wrong, every value is valid

Answering *"could this have been known at the time?"* needs a map spanning raw tables,
transformations, features and models. That map is DataHub's column-level lineage.

## What it does

Hindsight is a **release gate**. Point it at a model and it does four things, then hands you
an exit code your CI can act on.

**1. Trace it back.** It asks DataHub one question through the **Agent Context Kit**: is
there a path from this column to that one, and which way does it run? The answer comes back
with the middle hop naming a **query entity**, so the evidence cites the catalog's own record
of the transformation rather than a file we pointed it at.

**2. Check the clock.** For each source it compares when the rows became knowable against the
moment the decision had to be made. In the shipped loan example the decision is 10 Jan 2026
and the feature's data arrived 10 Feb 2026. **Thirty-one days too late.**

**3. Read the code.** It parses the transformation with `sqlglot` looking for an
`available_at <= prediction_time` guard. If a post-outcome source is joined with no guard,
that is proof, and no retraining is needed.

**4. Rebuild and re-test.** It reconstructs the feature in DuckDB using only records that
existed at the cutoff, retrains, and measures what survives. A leaked feature loses its
advantage. A legitimate one keeps it.

Then, **only after a human ticks approval**, it writes the finding back into DataHub as a
field tag, a structured verdict property, a linked audit Document and an active incident, and
**re-reads every one** to prove it persisted. A write that cannot be read back is treated as
a failure.

### The result that shows it is not theatre

| Feature | Importance (ablation delta) | Hindsight verdict |
|---|---:|---|
| Planted leaked feature | 0.21 | `confirmed`, blocked |
| Legitimate control | **0.24** | `clear_for_release` |

The **safe** feature scores higher, and Hindsight clears it anyway.

That is the whole argument. Importance tells you what a model leaned on. It cannot tell you
whether the model was **allowed to know it**. A detector built on importance flags exactly
the wrong feature here, which is why this pair is a permanent regression test rather than a
demo prop.

### What ships

- **Five audits across three industries**: loan approval, the same loan model after repair, a
  deliberately subtle variant, hospital readmission, and fraud screening. **One is expected to
  pass**, because a gate that can only say no is indistinguishable from one that is not
  looking.
- **A `scan-sql` mode** that walks a whole dbt project with no DataHub and no seeded data.
  Files it cannot parse are reported as **unchecked**, never as clean.
- **A feature sweep** for when you do not know which feature is guilty: it ranks every
  candidate by advantage lost to the cutoff, not by importance.
- **An evidence console** with a Plain English / Technical toggle, a printable record, and a
  panel listing every DataHub call the audit made, in order.
- **A DataHub Action deployment** that audits a model the moment it appears, with nobody
  triggering it.

## How we built it

A deterministic evidence engine with **no LLM in the decision path**. A language model may
explain evidence in prose. It can never promote a verdict.

Verdicts are a calibrated lattice: `insufficient_metadata` to `needs_review` to
`high_confidence` to `confirmed`, plus `clear_for_release`. `confirmed` is reachable by two
**independent** routes:

- a **deterministic SQL and time proof**, or
- a **point-in-time collapse**, where the advantage vanishes once the future is removed.

Either is sufficient alone, and the console reports **which one fired** rather than blending
them, so you can see exactly what settled it.

DataHub is reached through the **MCP Server** for discovery, lineage and governed mutations,
the **Agent Context Kit** for the column-level directional path query the whole project rests
on, and the **Python SDK** for typed ML metadata and write-back.

Stack: Python, DuckDB, sqlglot, scikit-learn, FastAPI and Jinja with no framework JavaScript.

## Challenges we ran into

**Importance cannot confirm leakage.** Our first verdict model let a plain ablation delta
reach `confirmed`. But removing *any* strong feature drops accuracy. We rebuilt the lattice so
importance is structurally unreachable as a confirmation branch, and added the higher-scoring
control that must come back clear on every run.

**A graphic that lied about time.** The cutoff timeline drew the decision line at 58% for
visual composition while the axis computed it at 52.9% from the real dates. On a graphic whose
entire job is being trusted about time, that is fatal. The window is now symmetric so a single
linear scale puts the cutoff at dead centre, and a test asserts the drawn line and the
computed tick agree.

**A status light that always said "connected."** The console asserted a healthy DataHub
connection whether or not one existed, which is precisely the kind of unevidenced claim this
project exists to catch. It now probes, distinguishes `not configured` from `unreachable`, and
disables publishing when the catalog cannot be written.

**A false negative wearing a pass.** Run against
[dbt-labs/jaffle-shop](https://github.com/dbt-labs/jaffle-shop), a public project written by
someone with no knowledge of this tool, every model came back clean. Jinja templating made
them unparseable, and unparseable was falling through to "no post-outcome source found". They
are now reported as **unchecked**, never as clean.

## Accomplishments that we're proud of

- **42 benchmark cases, 0 false positives, 0 false negatives**, sweeping the defect from
  reaching every record down to two percent of them. Below forty percent reach the statistical
  route stops firing and the deterministic proof still catches it. That is the measured
  argument for having two independent routes.
- **It works on data we did not create.** `examples/adapter/` is committed CSV in a different
  domain, with different column names and a different leak mechanism.
- **The control that cannot be allowed to fail.** The legitimate feature with the *higher*
  importance score is re-audited on every single run, and the build breaks if it is ever
  flagged. "It does not just block everything" is enforced, not asserted.
- **A frozen generator with a committed seed**, and the collapse threshold margin published
  (5.142 percentage points) rather than hidden. Whatever it produces is what we publish.
- **Three contributions back to DataHub**, all found by building this:
  [#18705](https://github.com/datahub-project/datahub/pull/18705) (merged) documents a
  required field the incidents tutorial omitted;
  [#18822](https://github.com/datahub-project/datahub/pull/18822) stops
  `datahub docker quickstart` crashing on legacy Windows code pages, which we only hit because
  we develop and run CI on Windows as well as Linux;
  [datahub-skills#68](https://github.com/datahub-project/datahub-skills/pull/68) adds an ML
  release-audit skill.

## What we learned

Being trusted matters more than being impressive.

Nearly every hard call came down to refusing to overstate. Publishing the threshold margin
instead of burying it. Keeping `insufficient_metadata` as a real answer, because "we could not
reach the catalog" is not evidence of anything. Separating `available` from `found` in the
lineage response, so an outage can never read as a clean bill of health. Saying plainly which
parts do not yet work on your own data.

The sharpest lesson came from our own bugs. Twice we shipped something that reported success
without checking: a status light that asserted a connection it never probed, and a scanner
that called unparseable files clean. Both are the exact failure this project exists to
prevent, and we only found them by testing against work we had not written ourselves.

## What's next for Hindsight

- **Direct warehouse adapters.** Point-in-time reconstruction already runs on mapped
  CSV/Parquet snapshots in long or wide form. Connecting straight to Snowflake and BigQuery is
  the remaining transport work.
- **The other two analyzers**: training and serving skew, and degenerate feedback loops where
  a model's own output re-enters its training data.
- **Upstreaming the skill**, so any DataHub user gets the release-audit workflow without
  installing us.

One honest boundary, stated here as it is in the README: point-in-time reconstruction needs an
availability timestamp. A nightly overwrite that keeps no history cannot be audited this way
by anyone, including us, because the information needed to answer the question was never
stored.
