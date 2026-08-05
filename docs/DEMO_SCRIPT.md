# Demo script

Target 2:45. Hard limit 3:00.

## The story in one breath

A model scored 100%. Everyone celebrated. Then it failed, because it had been reading the
answer. Nobody caught it, because the mistake happened earlier, deep in a pipeline the ML
team never opens, where only the catalog can see. Hindsight asks the catalog one question,
proves the model was cheating, and writes the proof back so nobody has to solve it twice.

Six beats. Each one sets up the next. Do not reorder them, because the payoff at 1:10 only
lands if the setup at 0:12 has happened.

| Beat | What it earns |
|---|---|
| 1. The hook | Attention |
| 2. Why nobody catches it | Why DataHub is necessary, not decorative |
| 3. The trace | Use of DataHub |
| 4. **The inversion** | Originality. The moment people remember |
| 5. It holds up | Technical execution |
| 6. The loop closes | Real-world usefulness |

## Before you record

```powershell
uv run datahub docker quickstart --quickstart-compose-file docker/datahub.quickstart.yml
uv run hindsight serve
curl http://127.0.0.1:8100/audits/latest    # warm the cache so no beat waits
```

Browser at 1600x1000, 100% zoom, dark theme. Hide bookmarks and extensions.

Three tabs, left to right:

| Tab | Opens on | Becomes |
|---|---|---|
| 1 | `http://127.0.0.1:8100/` | the audit, once you click a scenario in beat 4 |
| 2 | `http://127.0.0.1:8100/evidence` | unchanged |
| 3 | DataHub, searching `hindsight` | shows the tag after you publish |

You only ever move right, except once: beat 6 comes back to tab 1.

Record locally, not against the hosted demo. The hosted one is read-only by design, so it
cannot show the write-back. Mention the URL at the end instead.

Do one silent dry run first. The timings assume you are not hunting for a click.

---

## The script

Say the lines in your own words. They are written to be spoken, not read.

**Pace check.** 373 spoken words plus nine marked pauses. That is about **2:43** at a normal
pace, and **2:54** if you speak slowly. Both fit, but the second leaves very little room.

If your dry run passes 2:50, do not speed up and do not swallow the pauses. The pauses are
doing real work. Take the first item off the cut list and run it again.

Every beat is the same three lines: what to click, where to put the cursor, what to say.
Move the cursor first, wait a beat, then talk. Their eyes arrive before your sentence does.

### 1. The hook (0:00 to 0:12)

**Tab** `/` (landing page). You start here, nothing to click.
**Point at** the headline, then the two exam cards: **Scored in testing 100%** and
**Scored honestly 83%**.

> This model scored one hundred percent at predicting who would repay a loan.
>
> Everyone celebrated.
>
> Then it failed in production.

**Pause. Two full beats.**

> Why?

**Let the silence sit.** Do not fill it.

### 2. Why nobody catches it (0:12 to 0:47)

**Scroll** down the same page to "How can software know a model cheated?"
**Point at** the four steps as you reach them. Do not read them out.

> The model was never good. One fact it was shown could only be known *after* the
> decision had already been made.
>
> It wasn't predicting. It was reading the answer.

**Pause.**

> And the mistake wasn't where the model was built. It happened earlier, deep inside
> a data pipeline that nobody on the ML team ever looks at. By the time anyone
> notices, the money is gone.

**Pause. This next line is the turn.**

> One thing knows where every column came from.

**Pause. Look at the camera. Then, quietly:**

> The catalog.

### 3. The trace (0:47 to 1:10)

**Stay on the landing page.** Do not click a scenario yet, the trace lives here.
**Scroll** to "What the catalog actually answers".

> So instead of guessing, Hindsight asks DataHub one question, through its Agent
> Context Kit: where did this feature actually come from?

**Point at the middle hop of the path**, the long `urn:li:query:...` node. **Wait one beat.**

> This right here.
>
> This is where the answer leaked in. DataHub's column-level lineage doesn't just tell
> us these two columns are connected. It tells us exactly what turned one into the other.

### 4. The inversion (1:10 to 1:40)

This is the beat that wins. Slow down. Let the two bars sit on screen.

**Click** the **The hard case** scenario card. Say the first line while it loads.
**Click** the **Technical** toggle.
**Scroll** to "Importance gets this exactly backwards".

> Until now we have only been following the evidence. Here is the surprising part.

**Pause. Point at the two bars, longer one first. Then:**

> Two features. The legitimate one has the *higher* importance score. Hindsight
> clears that one, and blocks the lower one.
>
> If you ranked features by importance, which is what most tools do, you would get
> this exactly backwards. Importance tells you what the model leaned on. It cannot
> tell you whether the model was allowed to know it.

### 5. It holds up (1:40 to 2:14)

Two ideas only: forty-two, and two percent. Everything else on this screen is visual.

**Switch** to the `/evidence` tab.
**Scroll** to "What happens as the defect gets subtler".

> We tested this forty-two different ways. Even when the flaw touched only two
> percent of the data, Hindsight still caught it.

**Point at the colour change in the chart. Wait.**

> Watch what happens next. Past a certain point, performance alone can't tell the
> difference anymore. Only reading the code still finds it. That is why there are
> two independent checks.

**Scroll** to "Does it work on data we did not create?", then the sweep table below it.

> Then we ran it on data we did not create. Same conclusion. And when you do not know
> which feature is guilty, it checks all of them at once.

### 6. The loop closes (2:14 to 2:39)

**Switch back** to the audit tab from beat 4.
**Scroll** to "Publish evidence to DataHub".
**Tick** the approval checkbox, then **click** publish. Keep talking while it runs.

> When a person approves, and only then, it writes the finding back into DataHub. A
> tag on the column, the verdict, an audit document, an incident. Then it re-reads
> every one of them to prove it actually stuck.

**Switch** to the DataHub tab showing the tag on the column.

> So the next engineer inherits the answer instead of rediscovering it.

**Pause.**

> The same mistake never has to be solved twice.

### Close (2:39 to 2:46)

**Switch** to the `/evidence` tab, the contributions row near the bottom.

> Building this turned up three fixes for DataHub itself. One is already merged.
>
> Evidence, not intuition.

---

## If you run long

Cut in this order. Never cut beats 1, 3 or 4, and never cut the marked pauses.

1. The sweep sentence in beat 5, "and when you do not know which feature is guilty".
2. "By the time anyone notices, the money is gone."
3. The live publish. Say "already published, here is the record" and show
   `evidence/live/`. This is the riskiest live beat anyway.
4. The closing contributions line.

## Words to avoid saying

The screen can be technical. You should not be. Each of these has a plainer twin.

| Do not say | Say |
|---|---|
| statistical route | comparing performance |
| deterministic route | reading the code |
| point-in-time reconstruction | rebuilding it as of the decision |
| ablation delta | importance score |
| transformation | what turned one into the other |

## If something breaks mid-take

| Risk | What to do |
|---|---|
| Publish is slow or errors | You already have `evidence/live/2026-07-27.md`. Say "already published here" and show the DataHub tab. Do not re-record around it. |
| Status pill is not green | DataHub is not up. Start it, or record the offline path, but then do **not** claim a live write-back. |
| You fluff a line | Keep going and cut it in the edit. Re-takes cost more than one rough sentence. |

## Do not say

- Any number you have not shown on screen in that take.
- "Always", "guarantees", "never fails".
- Anything about other people's projects.
- That it works on any catalog today. Rebuilding a feature as of the decision needs an
  availability timestamp, and the README says so.

## After recording

- [ ] Under 3:00. Check the file, not your estimate.
- [ ] YouTube or Vimeo, **visibility public**. The rules say public, not unlisted.
- [ ] Watch it once at 1.5x with the sound off. If the story still reads, the visuals carry it.
- [ ] Paste the URL into `SUBMISSION.md` and the Devpost form.
- [ ] Put the live demo in the description:
      https://hindsight-production-abf8.up.railway.app
