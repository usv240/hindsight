# Isolated DataHub Action

Hindsight runs on the official DataHub Actions image instead of mixing the
Actions runtime into the main application environment. This avoids dependency
conflicts and makes the deployed runtime reproducible.

With the DataHub quickstart running, bind the Action to one exact ML-model URN:

```powershell
$env:HINDSIGHT_ACTION_TARGET_URN = "urn:li:mlModel:(urn:li:dataPlatform:mlflow,hindsight.credit_default_v1_leaky,PROD)"
$env:HINDSIGHT_ACTION_PIPELINE_NAME = "hindsight_release_gate_$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())"
docker compose -f docker/hindsight-action.compose.yml build
docker compose -f docker/hindsight-action.compose.yml up -d --force-recreate
```

The unique pipeline name creates a fresh Kafka consumer group. Start the Action
before emitting or changing the bound model because the runner intentionally
begins at the latest offset.

The pipeline consumes `mlModelProperties` upserts from DataHub's `MetadataChangeLogEvent_v1`, rejects unrelated
entity types and URNs, audits each bound model change while deduplicating exact redeliveries, and writes its local,
machine-readable result to `/tmp/hindsight-action-proof.jsonl` in the container.
It does not mutate catalog metadata; governed evidence write-back remains a
separate, human-approved operation.

Inspect the proof:

```powershell
docker exec docker-hindsight-release-gate-1 `
  sh -c "cat /tmp/hindsight-action-proof.jsonl"
```

The image build runs `pip check`. The verified proof and runtime details are in
[`evidence/integrations/2026-07-28.md`](../evidence/integrations/2026-07-28.md).
