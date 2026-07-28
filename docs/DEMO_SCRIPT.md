# Demo script — target 2:35

Written against the live console so nothing surprises you mid-take. Every beat names
what is on screen, what to click, and one line to say. Read it once, then record —
it should sound spoken, not read.

**The rules define "Submission Quality" as the video, description and README.** The
console only scores if the video shows it. This script is built so the strongest
artifacts — the ablation inversion, the timeline, the trust panel, the live write-back
— all appear inside three minutes.

## Before you record

```powershell
# 1. DataHub Core up, so the status pill reads "DataHub connected" (green)
#    http://localhost:9002 should answer

# 2. Console up
uv run hindsight serve

# 3. Warm the audit cache so no beat waits on a cold run
curl http://127.0.0.1:8100/audits/latest
```

- Browser at **1600×1000**, zoom 100%, **dark theme**.
- Hide bookmarks bar and any extension icons.
- Have four tabs pre-opened, in order: `/`, `/audits/latest`, DataHub search for
  `hindsight`, and the repo.
- Do a silent dry run first. The timings below assume you are not hunting for a click.

---

## The script

| Time | On screen | Say |
|---|---|---|
| **0:00–0:12** | `/` — the headline and the 100% → 83% cards | "A bank builds a model to predict who repays a loan. It scores almost perfectly in testing, so they ship it. And it fails." |
| **0:12–0:22** | Scroll slightly to the exam analogy | "The model was never good. It could see one fact that only existed *after* the decision was made. It wasn't predicting — it was reading the answer." |
| **0:22–0:32** | Scenario cards — hover across all five | "Hindsight catches that before release. Same defect, five situations — lending, healthcare, payments, the repaired version, and the hard one." |
| **0:32–0:42** | Click **The hard case** → lands on the audit | "Let's do the hard one. This is what leakage actually looks like in the wild — it only reaches about one record in seven." |
| **0:42–0:58** | The verdict block, then scroll to the timeline | "It scored 0.88 instead of 0.83. A small, plausible improvement — nobody would question it. Here's why they should." |
| **0:58–1:12** | **The timeline.** Point at the red cutoff line and the crossing bar | "Everything left of this line was knowable when the decision was made. Everything right of it did not exist yet. One feature reaches across." |
| **1:12–1:26** | Scroll to **How certain is this?** — the two routes | "There are two independent ways to prove this. On this case the statistical test *doesn't fire* — the signal is too small. The query itself gives it away." |
| **1:26–1:40** | Scroll to the **trust panel** | "Four ways a tool like this could be fooling you. A legitimate feature with a *bigger* importance score is audited every run and must come back clear. And one scenario is expected to pass — a gate with no yes isn't a gate." |
| **1:40–1:52** | Toggle to **Technical** → the ablation comparison | "This is the part that matters. The *safe* feature has the larger importance score. Hindsight blocks the shorter bar and clears the longer one. A detector built on importance gets this exactly backwards." |
| **1:52–2:06** | Scroll to **Backend activity**, click **Replay step by step** | "Every DataHub call, in order. It reads column-level lineage, checks availability against the cutoff, parses the SQL, rebuilds the feature point-in-time." |
| **2:06–2:22** | Tick approval → publish → switch to the DataHub tab showing the tag/incident | "On approval it writes the finding back into DataHub — a tag on the offending column, the verdict, an audit document, an open incident. Then re-reads every one to prove it stuck." |
| **2:22–2:35** | Back to `/audits` — the grouped table with the `ALLOW` row visible | "Four scenarios block. One clears. Evidence, not intuition." |

---

## Beats to protect if you run long

Cut in this order. Never cut the first two.

1. **Keep:** the ablation inversion (1:40) — the single most persuasive frame.
2. **Keep:** the timeline (0:58) — the clearest explanation of the defect.
3. Cut the activity-log replay to 6 seconds rather than dropping it.
4. Cut the trust panel to one sentence.
5. Cut the scenario hover.

## Things that will go wrong, and what to do

| Risk | Handling |
|---|---|
| Publish is slow or errors mid-take | You already have `evidence/live/2026-07-27.md` as proof. Say "already published here" and show the DataHub tab. Do not re-record around it. |
| The status pill is not green | DataHub isn't up. Either start it or record the offline path — but then do **not** claim a live write-back. |
| Cold audit causes a pause | The warm-up curl in the pre-flight prevents this. Re-run it if you restart the server. |
| You fluff a line | Keep going. Cut in the edit. Re-takes cost more than a rough sentence. |

## Do not say

- Any number you have not seen on screen in that take.
- "Always", "guarantees", "never fails".
- Anything about other people's projects.
- That it works on arbitrary catalogs today — it does not, and the README says so.

## After recording

- [ ] Under 3:00. Check the actual file, not your estimate.
- [ ] Upload to YouTube or Vimeo, **visibility public** (not unlisted — the rules say public).
- [ ] Watch it once at 1.5× with the sound off. If the story still reads, the visuals carry it.
- [ ] Paste the URL into `SUBMISSION.md` and the Devpost form.
