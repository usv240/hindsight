# Demo script

Target 2:45. Hard limit 3:00.

## The story in one breath

A model scored 100%. Everyone celebrated. Then it failed, because it had been reading the
answer. Nobody caught it, because the mistake happened earlier, deep in a pipeline the ML
team never opens, where only the catalog can see. Hindsight asks the catalog one question,
proves the model was cheating, and writes the proof back so nobody has to solve it twice.

Six beats. Each one sets up the next. Do not reorder them, because the payoff at 1:07 only
lands if the setup at 0:12 has happened.

| Beat | What it earns |
|---|---|
| 1. The hook | Attention |
| 2. Why nobody catches it | Why DataHub is necessary, not decorative |
| 3. The trace | Use of DataHub |
| 4. **The inversion** | Originality. The moment people remember |
| 5. It holds up | Technical execution |
| 6. The loop closes | Real-world usefulness |

## How to deliver it

The project is complicated. The explanation must not be. A judge should feel clever, not
like they are keeping up. Three habits do most of the work:

- **Point before you explain.** Move the cursor to the thing, wait one beat, then talk.
  Their eyes arrive before your sentence does.
- **Pause where it says pause.** The silences are marked. They are not padding, they are
  the part that makes the next line land.
- **Say "here is the interesting part" out loud.** Curiosity beats exposition. You are
  showing someone a discovery, not reading them a summary.

---

## Before you record

```powershell
uv run datahub docker quickstart --quickstart-compose-file docker/datahub.quickstart.yml
uv run hindsight serve
curl http://127.0.0.1:8100/audits/latest    # warm the cache so no beat waits
```

Browser at 1600x1000, 100% zoom, dark theme. Hide bookmarks and extensions.
Tabs in order: `/`, `/evidence`, a DataHub tab searching `hindsight`.

Record locally, not against the hosted demo. The hosted one is read-only by design, so it
cannot show the write-back. Mention the URL at the end instead.

Do one silent dry run first. The timings assume you are not hunting for a click.

---

## The script

Say the lines in your own words. They are written to be spoken, not read.

**Pace check.** About 370 spoken words, roughly 2:28 at 150 words a minute, plus about
12 seconds of marked pauses. That lands near 2:43. If your dry run passes 2:50, do not
speed up and do not swallow the pauses. Take the first item off the cut list and run again.

### 1. The hook (0:00 to 0:12)

**On screen:** the landing page. Headline and the 100% to 83% cards.

> Everyone celebrated. This model scored one hundred percent at predicting who
> would repay a loan.
>
> Then it failed in production.

**Pause. Two full beats.**

> Why?

**Let the silence sit.** Do not fill it.

### 2. Why nobody catches it (0:12 to 0:47)

**On screen:** scroll slowly to "How can software know a model cheated?"

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

**Pause. Then, quietly:**

> The catalog.

### 3. The trace (0:47 to 1:07)

**On screen:** click **The hard case**, scroll to "What the catalog actually answers".

> So instead of guessing, Hindsight asks DataHub to reconstruct exactly where this
> feature came from.

**Point at the middle of the path. Wait one beat.**

> This right here.
>
> That is the step DataHub found. It doesn't just tell us these two columns are
> connected. It tells us exactly what turned one into the other.

### 4. The inversion (1:07 to 1:37)

This is the beat that wins. Slow down. Let the two bars sit on screen.

**On screen:** open the audit, toggle **Technical**, the ablation comparison.

> Until now we have only been following the evidence. Here is the surprising part.

**Pause. Then:**

> Two features. The legitimate one has the *higher* importance score. Hindsight
> clears that one, and blocks the lower one.
>
> If you ranked features by importance, which is what most tools do, you would get
> this exactly backwards. Importance tells you what the model leaned on. It cannot
> tell you whether the model was allowed to know it.

### 5. It holds up (1:37 to 2:11)

Two ideas only: forty-two, and two percent. Everything else on this screen is visual.

**On screen:** `/evidence`, "What happens as the defect gets subtler".

> We tested this forty-two different ways. Even when the flaw touched only two
> percent of the data, Hindsight still caught it.

**Point at the colour change. Wait.**

> Here is the interesting part. Past a certain point, comparing performance stops
> working. Only reading the code still finds it. That is why there are two
> independent checks.

**On screen:** scroll to "Does it work on data we did not create?" and the sweep table.

> Then we ran it on data we did not create. Same conclusion. And when you do not know
> which feature is guilty, it checks all of them at once.

### 6. The loop closes (2:11 to 2:36)

**On screen:** back to the audit, tick approval, publish, then the DataHub tab showing the tag.

> When a person approves, and only then, it writes the finding back into DataHub. A
> tag on the column, the verdict, an audit document, an incident. Then it re-reads
> every one of them to prove it actually stuck.
>
> So the next engineer inherits the answer instead of rediscovering it.

**Pause.**

> The same mistake never has to be solved twice.

### Close (2:36 to 2:43)

**On screen:** the contributions row on `/evidence`.

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
