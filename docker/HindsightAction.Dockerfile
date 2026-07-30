# DataHub's own Actions runtime guarantees the Kafka/event contract and keeps
# its dependency stack isolated from Hindsight's modern SDK environment.
FROM acryldata/datahub-actions:v1.5.0.6-slim

USER root
WORKDIR /opt/hindsight

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY audits ./audits
COPY scenarios ./scenarios
COPY examples ./examples
COPY docker/hindsight-action.yml ./docker/hindsight-action.yml

RUN python -m pip install --no-cache-dir . && python -m pip check

ENV DATAHUB_TELEMETRY_ENABLED=false \
    PYTHONUNBUFFERED=1

ENTRYPOINT ["datahub", "actions", "run", "--debug", "-c", "docker/hindsight-action.yml"]

