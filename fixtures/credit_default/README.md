# Credit-default recorded fixture

This sanitized fixture lets judges reproduce Hindsight's evidence decisions
without Docker, DataHub, an LLM, or network access.

```powershell
uv run hindsight replay-fixture
```

The replay verifies every file against both `manifest.json` and `hashes.txt`
before reading recorded metadata. A mismatch fails closed with exit code `2`.

The fixture records semantic values rather than machine-specific DataHub URNs:

- dataset schema and field tag;
- upstream column-lineage direction and path;
- measured point-in-time validation output;
- unsafe transformation and verified remediation;
- expected unsafe and safe-control verdicts.

To prove the recording still represents a live local asset:

```powershell
uv run hindsight verify-fixture-live --target-urn "<synthetic-dataset-urn>"
```

After an intentional recapture, preview hash differences before changing the
integrity root:

```powershell
uv run python -m hindsight.fixtures.refresh
uv run python -m hindsight.fixtures.refresh --approve-refresh
uv run hindsight replay-fixture
```

Never approve a hash refresh merely to silence a failed integrity check. Review
the semantic diff first.
