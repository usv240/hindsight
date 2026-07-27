from __future__ import annotations

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

PROPERTY_URN = "urn:li:structuredProperty:hindsight.auditVerdict"


def run_probe(server: str, token: str | None = None) -> dict[str, Any]:
    """Prove structured-property, Document, and incident write-back against Core."""
    from datahub.sdk import DataHubClient, Dataset, Document

    client = DataHubClient(server=server, token=token)
    client.test_connection()
    suffix = str(int(time.time()))

    dataset = Dataset(
        platform="duckdb",
        name=f"hindsight.phase0.audit_target_{suffix}",
        description="Synthetic Phase 0 target for approved Hindsight write-back.",
        schema=[("application_id", "string"), ("risk_score", "double")],
    )
    client.entities.upsert(dataset)

    _ensure_structured_property(server, token)
    dataset.set_structured_property(PROPERTY_URN, ["high_confidence"])
    client.entities.upsert(dataset)
    reread_dataset = client.entities.get(dataset.urn)
    structured_property_passed = _has_property(
        reread_dataset.structured_properties, PROPERTY_URN, "high_confidence"
    )

    document = Document.create_document(
        id=f"hindsight-phase0-audit-{suffix}",
        title="Hindsight Phase 0 audit evidence",
        text=(
            "# Hindsight audit\n\n"
            "Verdict: `high_confidence`\n\n"
            "This synthetic record proves approved audit-document write-back."
        ),
        subtype="Audit",
        related_assets=[str(dataset.urn)],
        custom_properties={"hindsight_case_id": suffix},
        show_in_global_context=False,
    )
    client.entities.upsert(document)
    reread_document = client.entities.get(document.urn)
    document_passed = (
        reread_document.title == document.title
        and reread_document.text == document.text
        and str(dataset.urn) in (reread_document.related_assets or [])
    )

    incident_urn = _raise_incident(server, token, str(dataset.urn), suffix)
    incidents = _get_incidents_with_retry(server, token, str(dataset.urn))
    incident_passed = any(
        item.get("urn") == incident_urn
        and item.get("title") == "Hindsight release gate blocked"
        and item.get("status", {}).get("state") == "ACTIVE"
        for item in incidents
    )

    checks = {
        "structured_property_reread": structured_property_passed,
        "audit_document_reread": document_passed,
        "active_incident_reread": incident_passed,
    }
    return {
        "schema_version": 1,
        "captured_at": datetime.now(UTC).isoformat(),
        "server": server,
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "entities": {
            "dataset": str(dataset.urn),
            "document": str(document.urn),
            "incident": incident_urn,
            "structured_property": PROPERTY_URN,
        },
    }


def _ensure_structured_property(server: str, token: str | None) -> None:
    if _property_definition_ready(server, token):
        return

    mutation = """
      mutation CreateProperty($input: CreateStructuredPropertyInput!) {
        createStructuredProperty(input: $input) { urn }
      }
    """
    _graphql(
        server,
        token,
        mutation,
        {
            "input": {
                "id": "hindsight.auditVerdict",
                "qualifiedName": "hindsight.auditVerdict",
                "displayName": "Hindsight audit verdict",
                "description": "Deterministic ML release-audit verdict produced by Hindsight.",
                "valueType": "urn:li:dataType:datahub.string",
                "cardinality": "SINGLE",
                "entityTypes": [
                    "urn:li:entityType:datahub.dataset",
                    "urn:li:entityType:datahub.mlModel",
                ],
            }
        },
    )
    for attempt in range(10):
        if _property_definition_ready(server, token):
            return
        if attempt < 9:
            time.sleep(2)
    raise RuntimeError("Structured-property definition did not become readable within 20 seconds")


def _property_definition_ready(server: str, token: str | None) -> bool:
    data = _graphql(
        server,
        token,
        """
          query ExistingProperty($urn: String!) {
            structuredProperty(urn: $urn) { definition { qualifiedName } }
          }
        """,
        {"urn": PROPERTY_URN},
    )
    definition = (data.get("structuredProperty") or {}).get("definition") or {}
    return definition.get("qualifiedName") == "hindsight.auditVerdict"


def _raise_incident(server: str, token: str | None, dataset_urn: str, suffix: str) -> str:
    mutation = """
      mutation RaiseIncident($input: RaiseIncidentInput!) {
        raiseIncident(input: $input)
      }
    """
    data = _graphql(
        server,
        token,
        mutation,
        {
            "input": {
                "resourceUrn": dataset_urn,
                "type": "CUSTOM",
                "customType": "ML_LEAKAGE",
                "title": "Hindsight release gate blocked",
                "description": f"Synthetic Phase 0 leakage evidence, case {suffix}.",
            }
        },
    )
    incident_urn = data.get("raiseIncident")
    if not isinstance(incident_urn, str):
        raise RuntimeError(f"DataHub did not return an incident URN: {data}")
    return incident_urn


def _get_incidents_with_retry(
    server: str, token: str | None, dataset_urn: str
) -> list[dict[str, Any]]:
    query = """
      query AssetIncidents($urn: String!) {
        dataset(urn: $urn) {
          incidents(state: ACTIVE, start: 0, count: 20) {
            incidents { urn incidentType title description status { state } }
          }
        }
      }
    """
    for attempt in range(10):
        data = _graphql(server, token, query, {"urn": dataset_urn})
        incidents = ((data.get("dataset") or {}).get("incidents") or {}).get("incidents") or []
        if incidents:
            return incidents
        if attempt < 9:
            time.sleep(2)
    return []


def _has_property(assignments: Any, urn: str, expected: str) -> bool:
    return any(
        assignment.propertyUrn == urn and expected in assignment.values
        for assignment in (assignments or [])
    )


def _graphql(
    server: str, token: str | None, query: str, variables: dict[str, Any]
) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(
        server.rstrip("/") + "/api/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=30) as response:  # noqa: S310 - configured DataHub endpoint
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError(json.dumps(payload["errors"], indent=2))
    return payload.get("data") or {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default=os.getenv("DATAHUB_GMS_URL", "http://localhost:8080"))
    parser.add_argument("--token", default=os.getenv("DATAHUB_GMS_TOKEN"))
    parser.add_argument(
        "--output", type=Path, default=Path("evidence/phase0/writeback-roundtrip.local.json")
    )
    args = parser.parse_args()
    report = run_probe(args.server, args.token)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
