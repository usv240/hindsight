# Demo script — target 2:45

Written against the console as it stands today. Every beat names what is on screen,
what to click, and one line to say. Read it once, then record — it should sound
spoken, not read.

**The rules define "Submission Quality" as the video, description and README.**
Everything else only scores if the video shows it. There is now more strong material
than three minutes allows, so this script is built around one moment per judging
criterion rather than a tour.

| Criterion | The moment that earns it | Time |
|---|---|---|
| Use of DataHub | The query-entity trace | 1:00 |
| Originality | The ablation inversion | 1:20 |
| Technical Execution | The benchmark cliff | 1:40 |
| Real-World Usefulness | External data + the sweep | 2:00 |
| Contribution (bonus) | The merged PR | 2:35 |

---

## Before you record

```powershell
# 1. DataHub Core up, so the status pill reads "DataHub connected" (green)
uv run datahub docker quickstart --quickstart-compose-file docker/datahub.quickstart.yml

# 2. Console up
uv run hindsight serve

# 3. Warm the audit cache so no beat waits on a cold run
curl http://127.0.0.1:8100/audits/latest
```

- Browser at **1600×1000**, zoom 100%, **dark theme**.
- Hide the bookmarks bar and extension icons.
- Tabs pre-opened in order: `/`, `/audits/latest`, `/evidence`, DataHub search for
  `hindsight`.
- Do one silent dry run. The timings assume you are not hunting for a click.

**Record locally, not against the hosted demo.** The hosted one is read-only by
design, so it cannot show the write-back. Mention the URL at the end instead.

---

## The script

| Time | On screen | Say |
|---|---|---|
| **0:00–0:12** | `/` — headline and the 100% → 83% cards | "A bank builds a model to predict who repays a loan. It scores almost perfectly in testing, so they ship it. And it fails." |
| **0:12–0:22** | Scroll to the impact figures — 294 / 100k+ | "This is called target leakage. It's been found in 294 published papers and across a hundred thousand notebooks. It is not rare." |
| **0:22–0:32** | Same section, the two columns: Built for decisions with a clock / Not built for | "The model was never good. One fact it was shown only existed *after* the decision. It wasn't predicting — it was reading the answer." |
| **0:32–0:44** | Scenario cards → click **The hard case** | "Let's take the hard one, where the leak only reaches about one record in seven." |
| **0:44–0:58** | **What is being audited** panel — model name, feature, the 31-day gap | "It names the model, the feature, and the gap. The decision was made in January. That feature's data arrived in February." |
| **0:58–1:18** | Scroll to **What the catalog actually answers** — the trace | "Here's how it knew. It asks DataHub one question through the Agent Context Kit. Look at the middle of that path — that's a query entity. The catalog doesn't just say these columns are connected, it names the transformation that connects them." |
| **1:18–1:38** | Open the audit → toggle **Technical** → the ablation comparison | "Now the part that matters. The *legitimate* feature has the larger importance score. Hindsight blocks the shorter bar and clears the longer one. A detector built on importance gets this exactly backwards." |
| **1:38–2:00** | `/evidence` → **What happens as the defect gets subtler** | "Forty-two cases, swept from the defect reaching every record down to two percent. Every bar is full — it was caught every time. But watch the colour change. Below forty percent reach the statistical test goes blind, and only reading the code catches it. That's why there are two routes." |
| **2:00–2:22** | Scroll to **Does it work on data we did not create?** and the sweep table | "Our own scenarios are generated, so here's a different dataset entirely — subscription churn, committed CSV, downloadable. And when you don't know which feature is guilty, it sweeps all of them. Look at the second row: that feature scores 0.96 and loses nothing. Predictive and completely legitimate." |
| **2:22–2:36** | Back to the audit → tick approval → publish → DataHub tab showing the tag | "On approval it writes the finding into DataHub — a tag on the column, the verdict, an audit document, an incident. Then re-reads every one to prove it stuck." |
| **2:36–2:45** | `/evidence` → **Does this already exist?** and the contributions row | "Building this turned up a gap in DataHub's own docs. That fix is merged. Evidence, not intuition." |

---

## Beats to protect if you run long

Cut in this order. Never cut the first three.

1. **Keep:** the query-entity trace (0:58) — this is the Use-of-DataHub criterion.
2. **Keep:** the ablation inversion (1:18) — the single most persuasive frame.
3. **Keep:** the benchmark cliff (1:38) — the argument for the whole design.
4. Trim the impact figures to one sentence.
5. Trim the sweep to just the second row.
6. Drop the live publish and say "already published — here is the record", showing
   `evidence/live/`. The write-back is the riskiest live beat.
7. Drop the "what is being audited" panel and let the verdict card carry it.

## Things that will go wrong, and what to do

| Risk | Handling |
|---|---|
| Publish is slow or errors mid-take | You already have `evidence/live/2026-07-27.md`. Say "already published here" and show the DataHub tab. Do not re-record around it. |
| The status pill is not green | DataHub isn't up. Start it, or record the offline path — but then do **not** claim a live write-back. |
| Cold audit causes a pause | The warm-up curl prevents this. Re-run it if you restart the server. |
| You fluff a line | Keep going. Cut in the edit. Re-takes cost more than a rough sentence. |

## Do not say

- Any number you have not seen on screen in that take.
- "Always", "guarantees", "never fails".
- Anything about other people's projects.
- That it works on any catalog today. Point-in-time reconstruction needs an
  availability timestamp, and the README says so.

## After recording

- [ ] Under 3:00. Check the file, not your estimate.
- [ ] Upload to YouTube or Vimeo, **visibility public** — the rules say public, not unlisted.
- [ ] Watch it once at 1.5× with the sound off. If the story still reads, the visuals carry it.
- [ ] Paste the URL into `SUBMISSION.md` and the Devpost form.
- [ ] Mention the live demo URL in the description:
      https://hindsight-production-abf8.up.railway.app
