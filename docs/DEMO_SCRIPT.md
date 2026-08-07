# Demo script

Target 2:45. Hard limit 3:00.

## What the rules require

Checked against the official rules, not the overview page.

| Rule | What it means here |
|---|---|
| "less than three (3) minutes. Judges are not required to watch beyond three minutes" | Going over is not a disqualification, it is worse. They simply stop, and the ending is the part they never see. |
| "uploaded to and made publicly visible on YouTube, Vimeo, or Youku" | Public, not unlisted. |
| "footage that shows the Project functioning on the device for which it was built" | Record the real console running, not slides. |
| "must not include third party trademarks, or copyrighted music or other material unless the Entrant has permission" | **No music.** DataHub's own UI is the subject of the demo and is fine. Every other company's logo stays off screen, including in browser tabs, bookmarks and the OS bar. |
| All materials in English | The script is. |

The repository must also be public with an Apache 2.0 licence file, "detectable and visible
at the top of the repository page (in the About section)". That is a submission step, not a
recording step, but it is a hard requirement.

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

Browser at 1600x1000, 100% zoom, dark theme. Hide bookmarks and extensions, and close any
tab whose favicon is another company's logo. The rules forbid third-party trademarks you do
not have permission for, and a stray tab is the likeliest way one appears.

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

**Pace check.** 381 spoken words plus nine marked pauses. That is **2:46** at a normal
pace and **2:56** if you speak slowly.

Judges are not required to watch past 3:00, so overrunning does not get you penalised,
it gets your ending deleted. A slow read has only four seconds of margin, so do a timed
dry run before the real take. If it passes 2:50, take the first item off the cut list.
Do not speed up and do not swallow the pauses.

The landing page is one continuous scroll, top to bottom. Say what you are passing as you
pass it, so nothing appears without an explanation. Move the cursor first, wait a beat, then
talk. Their eyes arrive before your sentence does.

The whole demo uses one scenario, **Loan approval**, because that is the story you open with.

### 1. The hook (0:00 to 0:12)

**Where** tab 1, landing page, at the top. Nothing to click.
**Point at** the headline, then the two cards: **Scored in testing 100%** and
**Scored honestly 83%**.

> This model scored one hundred percent at predicting who would repay a loan.
>
> Everyone celebrated.
>
> Then it failed in production.

**Pause. Two full beats.**

> Why?

**Let the silence sit.** Do not fill it.

### 2. Why nobody catches it (0:12 to 0:52)

**Scroll** down one section, to "How often does this actually happen?"
**Point at** the figures as you arrive.

> The model was never good. One fact it was shown could only be known *after* the
> decision had already been made.
>
> It wasn't predicting. It was reading the answer.

**Pause.**

> And it is not rare. These are the studies that found it.
>
> The mistake wasn't where the model was built. It happened earlier, in a data
> pipeline nobody on the ML team ever looks at. By the time anyone notices, the
> money is gone.

**Pause. This next line is the turn.**

> One thing knows where every column came from.

**Pause. Look at the camera. Then, quietly:**

> The catalog.

### 3. The trace (0:52 to 1:20)

**Keep scrolling** in the same direction. You will pass "Pick a situation you recognise",
which holds five scenario cards. Say the first line while it goes by, then stop at
"What the catalog actually answers".

> Five situations here. We will run the loan one in a moment.
>
> Because instead of guessing, Hindsight asks DataHub one question, through its Agent
> Context Kit: where did this feature actually come from?

**Point at the middle hop of the path**, the long `urn:li:query:...` node. **Wait one beat.**

> This right here is where the answer leaked in. DataHub's column-level lineage doesn't
> just tell us these two columns are connected. It tells us what turned one into the other.

### 4. The inversion (1:20 to 1:50)

This is the beat that wins. Slow down. Let the two bars sit on screen.

**Scroll back up** to "Pick a situation you recognise" and **click the first card,
Loan approval**. It runs the audit and lands on the result. Say the first line while it runs.
**Click** the **Technical** toggle, then **scroll** to
"Importance gets this exactly backwards".

> Until now we have only been following the evidence. Here is the surprising part.

**Pause. Point at the two bars, longer one first. Then:**

> Two features. The legitimate one has the *higher* importance score. Hindsight
> clears that one, and blocks the lower one.
>
> If you ranked features by importance, which is what most tools do, you would get
> this exactly backwards. Importance tells you what the model leaned on. It cannot
> tell you whether the model was allowed to know it.

### 5. It holds up (1:50 to 2:20)

Two ideas only: forty-two, and two percent. Everything else here is visual.

**Switch** to tab 2, `/evidence`, and **scroll** to
"What happens as the defect gets subtler".

> We tested this forty-two different ways. Even when the flaw touched only two
> percent of the data, Hindsight still caught it.

**Point at the colour change in the chart. Wait.**

> Watch what happens next. Past a certain point, performance alone can't tell the
> difference anymore. Only reading the code still finds it. That is why there are
> two independent checks.

**Scroll** to "Does it work on data we did not create?"

> Then we ran it on data we did not create. Same conclusion. And it can sweep every
> feature at once.

### 6. The loop closes (2:20 to 2:44)

**Switch back** to tab 1, which is now the loan audit.
**Scroll** to "Publish evidence to DataHub".
**Tick** the approval checkbox, then **click** publish. Keep talking while it runs.

> When a person approves, and only then, it writes the finding back into DataHub. A
> tag, the verdict, an audit document, an incident. Then it re-reads every one to
> prove it stuck.

**Switch** to tab 3, DataHub, showing the tag on the column.

> So the next engineer, or the next agent, inherits the answer instead of
> rediscovering it.

**Pause.**

> The same mistake never has to be solved twice.

### Close (2:44 to 2:51)

**Switch** to tab 2 and **scroll** to the contributions row near the bottom.

> Building this turned up three fixes for DataHub itself. One is already merged.
>
> Evidence, not intuition.

---

## If you run long

Cut in this order. Never cut beats 1, 3 or 4, and never cut the marked pauses.

1. Beat 5, "And it can sweep every feature at once." Saves about 4 seconds.
2. Beat 2, "These are the studies that found it." Keep "And it is not rare", which is
   what stops the figures appearing unexplained.
3. Beat 2, "By the time anyone notices, the money is gone."
4. The live publish. Say "already published, here is the record" and show
   `evidence/live/`. This is the riskiest live beat anyway.
5. The closing contributions line.

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
- [ ] YouTube, Vimeo or Youku, **visibility public**. The rules say publicly visible, not unlisted.
- [ ] No music on the track. Copyrighted audio breaches the rules and is the easiest way to fail one.
- [ ] Watch it once at 1.5x with the sound off. If the story still reads, the visuals carry it.
- [ ] Paste the URL into `SUBMISSION.md` and the Devpost form.
- [ ] Put the live demo in the description:
      https://hindsight-production-dd6e.up.railway.app
