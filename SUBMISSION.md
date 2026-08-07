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

## Built with

`python` · `datahub` · `mcp` · `duckdb` · `sqlglot` · `scikit-learn` · `fastapi` · `jinja` · `htmx` · `numpy` · `pytest` · `github-actions`

---

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

## Feedback survey

Opt in. Feedback to give: fine-grained lineage emission needs a worked end-to-end example in the docs; the Analytics Agent quickstart is bash-only and needs a documented Windows/WSL2 path.
