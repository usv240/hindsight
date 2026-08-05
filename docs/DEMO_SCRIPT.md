# Demo script

Target 2:45. Hard limit 3:00.

## The story in one breath

A model scored 100%. They shipped it. It failed, because it had been reading the answer.
Nobody caught it, because the mistake was upstream in the warehouse, where only the catalog
can see. Hindsight asks the catalog one question, proves the model was cheating, and writes
the proof back so the next engineer inherits it.

Six beats. Each one sets up the next. Do not reorder them, because the payoff at 1:15 only
lands if the setup at 0:26 has happened.

| Beat | What it earns |
|---|---|
| 1. The hook | Attention |
| 2. Why nobody catches it | Why DataHub is necessary, not decorative |
| 3. The trace | Use of DataHub |
| 4. **The inversion** | Originality. The moment people remember |
| 5. It holds up | Technical execution |
| 6. The loop closes | Real-world usefulness |

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

**Pace check.** This is about 375 spoken words. At 150 words a minute that is 2:30 of
speech, leaving roughly 15 seconds for pauses, clicks and scrolling. If your dry run comes
in over 2:50, do not speed up. Take the first item off the cut list below and run it again.

### 1. The hook (0:00 to 0:12)

**On screen:** the landing page. Headline and the 100% to 83% cards.

> This model scored one hundred percent at predicting who would repay a loan.
> The bank shipped it. It started losing money immediately.

### 2. The twist, then why nobody catches it (0:12 to 0:45)

**On screen:** scroll slowly to "How can software know a model cheated?"

> The model was never good. One fact it was shown could only be known *after* the
> decision was already made. It wasn't predicting. It was reading the answer.
>
> And this is why it gets missed. The mistake wasn't in the notebook. It was three
> joins upstream, in a pipeline nobody on the model team opens. Monitoring finds it
> months later, once the losses arrive.

Beat. Then, slower:

> One thing knows where every column came from. The catalog.

### 3. The trace (0:45 to 1:12)

**On screen:** click **The hard case**, scroll to "What the catalog actually answers".

> So Hindsight asks DataHub one question, through the Agent Context Kit. Is there a
> path from this column to that one, and which way does it run?
>
> Look at the middle of that path. That is a query entity. DataHub doesn't just say
> these columns are connected. It names the transformation that connects them. Not a
> file I pointed the tool at. The catalog's own record.

### 4. The inversion (1:12 to 1:40)

This is the beat that wins. Slow down. Let the two bars sit on screen.

**On screen:** open the audit, toggle **Technical**, the ablation comparison.

> Now the part I would watch. Two features. The legitimate one has the *higher*
> importance score. Hindsight clears that one, and blocks the lower one.
>
> If you ranked features by importance, which is what most tools do, you would get
> this exactly backwards. Importance tells you what the model leaned on. It cannot
> tell you whether the model was allowed to know it.

### 5. It holds up (1:40 to 2:15)

**On screen:** `/evidence`, "What happens as the defect gets subtler".

> Forty-two cases, from the flaw touching every record down to two percent. Caught
> every time. But watch the colour change. Below forty percent the statistical test
> goes blind, and only reading the code still catches it. That is why there are two
> routes, measured rather than claimed.

**On screen:** scroll to "Does it work on data we did not create?" and the sweep table.

> Our scenarios are generated, so here is a dataset we did not make. And when you do
> not know which feature is guilty, it sweeps all of them.
>
> Second row. Point nine six, and loses nothing. Predictive, and completely legitimate.

### 6. The loop closes (2:15 to 2:38)

**On screen:** back to the audit, tick approval, publish, then the DataHub tab showing the tag.

> When a person approves, and only then, it writes the finding back into DataHub. A
> tag on the column, the verdict, an audit document, an incident. Then it re-reads
> every one of them to prove it actually stuck.
>
> So the next engineer inherits the answer instead of rediscovering it.

### Close (2:38 to 2:45)

**On screen:** the contributions row on `/evidence`.

> Building this turned up three fixes for DataHub itself. One is already merged.
>
> Evidence, not intuition.

---

## If you run long

Cut in this order. Never cut beats 1, 3 or 4.

1. The sweep table. Keep the external dataset sentence, drop the second row.
2. The analogy line about the student.
3. The live publish. Say "already published, here is the record" and show
   `evidence/live/`. This is the riskiest live beat anyway.
4. The closing contributions line.

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
- That it works on any catalog today. Point-in-time reconstruction needs an availability
  timestamp, and the README says so.

## After recording

- [ ] Under 3:00. Check the file, not your estimate.
- [ ] YouTube or Vimeo, **visibility public**. The rules say public, not unlisted.
- [ ] Watch it once at 1.5x with the sound off. If the story still reads, the visuals carry it.
- [ ] Paste the URL into `SUBMISSION.md` and the Devpost form.
- [ ] Put the live demo in the description:
      https://hindsight-production-abf8.up.railway.app
