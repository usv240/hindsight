# Hindsight

> Your model is not smarter. It has hindsight.

Hindsight is an evidence-based ML release gate that uses DataHub column lineage and time semantics to catch target and temporal leakage before a model is promoted. Deterministic evidence decides the verdict; an LLM may explain evidence but cannot promote it.

## Judge quick start

```powershell
uv sync --extra dev
uv run hindsight demo
```

That single command runs the unsafe case, the high-correlation safe control, both independent confirmation routes, fixture integrity checks, and the central regression argument. It requires no Docker, DataHub, network, warehouse, or LLM and returns in well under a minute.

To open the evidence console:

```powershell
uv run hindsight serve
```

Then visit `http://127.0.0.1:8100`. See [QUICKSTART.md](QUICKSTART.md) for the full live DataHub path.

## The result an ablation detector gets backwards

| Feature | Ablation delta | Hindsight verdict |
|---|---:|---|
| Planted post-outcome feature | 0.21 | `confirmed` |
| Legitimate pre-cutoff control | **0.24** | `clear_for_release` |

The safe feature matters more by ablation, yet Hindsight clears it. Feature importance is not evidence that information was legally available at prediction time.

## Two independent confirmation routes

Hindsight deliberately keeps two artifacts separate:

1. [confirmed_leakage.case.json](examples/confirmed_leakage.case.json) isolates the deterministic SQL/time route. Its `point_in_time_advantage_collapsed` flag is intentionally `false` because deterministic cutoff proof alone confirms that case.
2. The [recorded fixture](fixtures/credit_default/README.md) exercises the independent point-in-time route for the same planted defect mechanism. It removes post-cutoff records, reruns the evidence comparison, and confirms the collapse.

They are complementary proofs, not conflicting measurements.

## Honest synthetic-demo disclosures

The planted synthetic leak is **total by construction**, so its observed AUC of `1.000000` is expected. Real leakage can be subtler. The generator is frozen; Hindsight reports the measured result rather than retuning it to look realistic.

The point-in-time demo defines collapse as a strict majority of the apparent advantage disappearing. The `50%` boundary is a visible, configurable demo policy—not a universal scientific constant. It cannot confirm leakage by itself: the deterministic engine also requires directional post-outcome lineage and an authoritative availability-time violation.

Measured reconstruction:

| Measure | Observed | Point-in-time |
|---|---:|---:|
| Planted case AUC | 1.000000 | 0.833630 |
| Advantage over baseline | 0.301712 | 0.135342 |
| Advantage retained | — | 44.858% |
| Legitimate control AUC | 0.924842 | 0.924842 |

See [evaluations/results.json](evaluations/results.json).

## Evidence contract

- `insufficient_metadata`: required lineage or time evidence is absent.
- `needs_review`: ancestry is suspicious, but direction or time is unproven.
- `high_confidence`: directional outcome lineage and an availability violation are established.
- `confirmed`: deterministic cutoff proof or qualified point-in-time reconstruction confirms the violation.
- `clear_for_release`: configured checks and planted safe controls pass.

Plain ablation is explanatory context only. It is unreachable as a confirmation branch in the verdict engine.

## DataHub execution

The live path uses DataHub Core, the Python SDK, and the official MCP server to:

- retrieve fine-grained column lineage and transformation context;
- verify field tags and governed metadata through MCP;
- publish an approved confirmed tag, structured verdict, linked audit Document, and active incident;
- reread every mutation;
- reuse the same active incident on retry.

Publication is dry-run by default and requires explicit `--approve-writeback`. Evidence is recorded under [evidence](evidence/).

## Reusable DataHub Skill

The upstream-shaped [DataHub ML Release Audit Skill](skills/datahub-ml-release-audit/SKILL.md) turns Hindsight's calibrated evidence protocol into a reusable Agent Skill. It includes the verdict contract, MCP/CLI workflow, human-approved writeback rules, and a deterministic evidence-bundle validator. The local contribution is tested; an upstream pull request remains external work and is not claimed as complete.

## Useful commands

```powershell
uv run hindsight demo --json
uv run hindsight replay-fixture
uv run hindsight demo-audit --output evidence/demo-audit.local.json
uv run hindsight verify-sql examples/leaky_feature.sql --post-outcome-table payment_events_after_decision
uv run hindsight publish-audit --target-urn "<synthetic-dataset-urn>"
uv run hindsight publish-audit --target-urn "<synthetic-dataset-urn>" --approve-writeback
uv run pytest
```

`demo` returns `0` when the demonstration reproduces all expected outcomes. Release-gate commands retain separate CI semantics: `0` clear, `2` incomplete/review, and `3` block.

## Reproducibility

- 29 tests pass, including the single-command judge regression and Skill contract tests.
- Offline recorded-fixture replay: approximately `0.023s`, target `<60s`.
- Point-in-time reconstruction: approximately `0.159s` for 4,000 applications.
- Apache License 2.0.
- Raw `*.local.json`, environments, caches, and build outputs are ignored.

## License

Apache License 2.0. See [LICENSE](LICENSE).
