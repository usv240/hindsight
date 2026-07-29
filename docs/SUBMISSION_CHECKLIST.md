# Submission checklist

Checked line-by-line against the official rules. Status as of 2026-07-28.

## Required

| # | Requirement | Status |
|---|---|---|
| 1 | Working software application using DataHub | ✅ 168 tests, CI green, live end-to-end proof in `evidence/live/` |
| 2 | Addresses a challenge track | ✅ Production ML Agents |
| 3 | URL judges can use to test functionality | ⬜ **Blocked until repo is public**; then `uv run hindsight demo` works with no Docker in <1 min |
| 4 | Public code repository | ⬜ **Repo is private — flip at submission** (see below) |
| 5 | Repo contains all source, assets, full instructions | ✅ `README.md`, `QUICKSTART.md`, `audits/README.md`, `docs/img/README.md` |
| 6 | Apache 2.0 licence, detectable in the About section | ✅ Verified: GitHub reports `{"licenseInfo":{"key":"apache-2.0"}}` |
| 7 | Text description of the project | ✅ `SUBMISSION.md` |
| 8 | Demo video < 3 min, public, YouTube/Vimeo | ⬜ **Outstanding — user is recording** |
| 9 | Sample outputs in an `examples/` folder | ✅ `examples/` — cases, SQL, audit document, CI workflow |
| 10 | Newly created during the submission period | ✅ Full commit history from 2026-07-27 |
| 11 | English submission materials | ✅ |
| 12 | No third-party rights issues | ✅ All data synthetic; no real personal data anywhere |

## Judging criteria

| Criterion | Evidence |
|---|---|
| **Use of DataHub** | Column-level lineage + ML entities read via official MCP server and Python SDK. Writes back a field tag, structured property, audit Document and active incident — each re-read to prove persistence. Named in the default plain-English view, not buried in a technical tab. |
| **Technical execution** | Deterministic engine, LLM structurally outside the decision path. 168 tests. CI on Ubuntu + Windows × Python 3.11 + 3.12. ASCII-console and JSON-deliverable guards. |
| **Originality** | Cross-pipeline leakage detection. Existing research (Yang et al., ASE 2022) is notebook-scoped; this catches leaks originating in the warehouse. Not a feature DataHub ships. |
| **Real-world usefulness** | CI release gate with exit codes, copyable workflow in `examples/ci/`, three industry scenarios. Boundaries stated honestly in the README. |
| **Submission quality** | Plain-English mode by default, six generated screenshots, mermaid architecture diagram, research citations. |
| **Bonus: OSS contribution** | Two PRs, both arising from building this. `datahub#18705` (required `customType` on `CUSTOM` incidents) is **merged**. `datahub-skills#68` (the `datahub-ml-release-audit` skill) is open and awaiting review. |

## Final steps at submission time

```bash
# 1. Make the repo public (kept private until now so competitors could not copy it)
gh repo edit usv240/hindsight --visibility public --accept-visibility-change-consequences

# 2. Confirm the licence badge renders in the About section
gh repo view usv240/hindsight --json licenseInfo,visibility

# 3. Paste into the Devpost form from SUBMISSION.md, plus:
#    - the video URL
#    - the datahub-skills PR URL
#
# 4. Opt in to the Most Valuable Feedback survey (feedback text is in SUBMISSION.md)
```

## Deliberately out of scope

Stated plainly rather than left as gaps a judge might find:

- **Point-in-time reconstruction on arbitrary warehouse schemas.** Expects the seeded
  scenario's data shape. The SQL checks, verdict lattice and DataHub write-back are already
  generic. Documented in the README's maturity table.
- **Console authentication.** Binds to loopback, protects state-changing forms with CSRF tokens, and requires an exact write-back target; an authenticating proxy is still required beyond loopback.
  Needs an authenticating proxy before any real exposure.
- **True call-level instrumentation of the activity log.** Entries are derived from real
  artifacts and labelled `RECORDED` vs `LIVE`, but are not emitted by instrumented calls.
