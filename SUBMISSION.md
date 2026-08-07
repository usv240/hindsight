# Devpost submission

Everything the submission form asks for, ready to paste. Kept in the repo so the
claims here and the code stay in sync.

---

## Project name

**Hindsight**

## Elevator pitch (Devpost field, max 200 chars)

Paste this one. 172 characters, no em dashes.

> A model that scores 100% is usually cheating. Hindsight uses DataHub column lineage to prove a feature knew the answer before the decision was made, and blocks the release.

Alternatives if you want a different emphasis:

- **Longer, states the method first** (188 chars): Models that score perfectly are often just cheating. Hindsight uses DataHub column lineage to prove whether a feature knew the answer before the decision was made, then blocks the release.
- **Shortest, uses the repo strapline** (134 chars): Your model is not smarter, it has hindsight. Proves target leakage from DataHub column lineage and blocks the release before it ships.

## Thumbnail

`docs/img/devpost-thumbnail.png` - 2400x1600, exactly 3:2, 596 KB, well under the 5 MB cap.

Cropped from a real capture of the console, so it cannot show anything the tool does not
render. It carries the headline, the 100% to 83% comparison that is the whole idea, and the
green "DataHub connected" pill.

## Challenge track

**Production ML Agents** (also demonstrates Agents That Do Real Work)

## Built with (Devpost tags, max 25)

Verified against `pyproject.toml` and the repo. 16 tags:

```
python  datahub  mcp  agent-context-kit  duckdb  sqlglot  scikit-learn
fastapi  jinja  uvicorn  docker  railway  github-actions  pytest  ruff  uv
```

Two tags were in an earlier draft and are **wrong**, do not add them: `htmx` (no htmx
anywhere in the templates or static files) and `numpy` (arrives only transitively via
scikit-learn, not a declared dependency).

## Try it out links

1. `https://hindsight-production-dd6e.up.railway.app` - live demo, five real audits, nothing
   to install
2. `https://github.com/usv240/hindsight` - source, Apache 2.0

## Image gallery

Ten images in `docs/img/gallery/`, all exactly 3:2 as the form asks, 3.6 MB total. Upload in
filename order; they tell the story in the same sequence as the video.

| File | What a judge sees |
|---|---|
| `01-the-problem.png` | Scored 100% in testing, 83% once the answer was taken away |
| `02-how-it-works.png` | The four steps, and the one that needs a catalog |
| `03-datahub-lineage.png` | The query entity in the column path, Agent Context Kit named |
| `04-what-is-audited.png` | The model, the feature, and the 31 day gap |
| `05-agent-activity.png` | Every DataHub call in order, including the MCP Server |
| `06-the-inversion.png` | The legitimate feature scores higher and is cleared anyway |
| `07-timeline.png` | The one feature that reaches past the decision |
| `08-writeback.png` | Four records written to DataHub, each re-read |
| `09-benchmark.png` | 42 cases, 0 false positives, 0 false negatives |
| `10-external-data.png` | Run on a dataset we did not create |

Regenerate with `uv run python scripts/capture_gallery.py` while `hindsight serve` is running.
Sections are located by heading id, so a layout change moves the crop rather than silently
capturing the wrong thing.

## Project story (the big "About the project" box)

The full text is in [`docs/DEVPOST_STORY.md`](docs/DEVPOST_STORY.md), written against
Devpost's seven headings so it pastes straight in. 1,491 words, no em dashes, no emoji.

Every figure in it is checked against the repo: 42 benchmark cases with 0 false positives and
0 false negatives, 309 tests, the 5.142 point threshold margin, the 0.21 against 0.24
ablation inversion, and three upstream pull requests.

Citations used, all verifiable:

- Kaufman, Rosset & Perlich, *Leakage in Data Mining*, KDD 2011
- Yang, Brower-Sinning, Lewis & Kästner, *Data Leakage in Notebooks*, ASE 2022,
  [arXiv:2209.03345](https://arxiv.org/abs/2209.03345)
- Kapoor & Narayanan, *Leakage and the Reproducibility Crisis in ML-based Science*,
  Patterns 2023

---

## Testing instructions for judges

**Fastest path** (no Docker, no DataHub, no API key, under a minute):

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

**Full live path**, local DataHub Core, MCP server, and approved write-back: see `QUICKSTART.md`.

## Links

- **Live demo:** https://hindsight-production-dd6e.up.railway.app - read-only, five real audits, nothing to install
- **Repository:** https://github.com/usv240/hindsight
- **Open-source contributions:**
  - [datahub#18705](https://github.com/datahub-project/datahub/pull/18705), **merged**: documents the required `customType` field on `CUSTOM` incidents, which the tutorial omitted. Hit while building Hindsight's incident write-back; following the guide as written returns `customType is required: Failed to create incident.`
  - [datahub#18822](https://github.com/datahub-project/datahub/pull/18822), open: stops `datahub docker quickstart` raising `UnicodeEncodeError` on legacy Windows code pages. Hit bringing DataHub up for this project; the stack was already healthy, so a working install reported failure.
  - [datahub-skills#68](https://github.com/datahub-project/datahub-skills/pull/68), open: adds the `datahub-ml-release-audit` skill.
- **Demo video:** _paste URL here_

## Additional info and Feedback Prize

The judges-only step and all four feedback answers are in
[`docs/DEVPOST_ADDITIONAL_INFO.md`](docs/DEVPOST_ADDITIONAL_INFO.md), including which DataHub
technology boxes to tick and, more importantly, the one to leave alone.

Quick reference:

- **Challenge category:** Production ML Agents
- **DataHub technologies:** Core Platform, MCP Server, Agent Context Kit, Skills, and Actions
  under "Other". Not Analytics Agent, we did not use it.
- **Newly created in the window:** yes, first commit 2026-07-27, latest 2026-08-07
- **Country of residence:** yours to fill in
