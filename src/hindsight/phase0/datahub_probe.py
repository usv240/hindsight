from __future__ import annotations

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def run_probe(server: str, token: str | None = None) -> dict[str, Any]:
    """Emit and reread schema, field tag, and fine-grained lineage in DataHub Core."""
    from datahub.metadata.urns import DatasetUrn, TagUrn
    from datahub.sdk import DataHubClient, Dataset

    client = DataHubClient(server=server, token=token)
    client.test_connection()

    suffix = str(int(time.time()))
    upstream_name = f"hindsight.phase0.payment_events_{suffix}"
    downstream_name = f"hindsight.phase0.leaky_features_{suffix}"
    tag_name = "hindsight:leakage-candidate"

    upstream = Dataset(
        platform="duckdb",
        name=upstream_name,
        description="Phase 0 source containing post-decision payment events.",
        schema=[
            ("application_id", "string", "Synthetic application identifier"),
            ("payment_recorded_at", "timestamp", "Availability time of payment event"),
        ],
    )
    downstream = Dataset(
        platform="duckdb",
        name=downstream_name,
        description="Phase 0 feature output used to prove Hindsight lineage round trips.",
        schema=[
            ("application_id", "string", "Synthetic application identifier"),
            ("days_since_last_payment", "integer", "Candidate temporal-leakage feature"),
        ],
    )
    downstream.schema[1].add_tag(TagUrn(tag_name))

    client.entities.upsert(upstream)
    client.entities.upsert(downstream)
    client.lineage.add_lineage(
        upstream=upstream.urn,
        downstream=downstream.urn,
        column_lineage={"days_since_last_payment": ["payment_recorded_at"]},
        transformation_text=(
            "SELECT date_diff('day', payment_recorded_at, decision_at) "
            "AS days_since_last_payment FROM payment_events"
        ),
    )

    downstream_urn = DatasetUrn(platform="duckdb", name=downstream_name)
    lineage = _get_lineage_with_retry(
        client,
        downstream_urn,
        source_column="days_since_last_payment",
        attempts=10,
        delay_seconds=2,
    )
    reread = client.entities.get(downstream.urn)
    tagged_field = next(
        field for field in reread.schema if field.field_path == "days_since_last_payment"
    )

    serialized_lineage = [_serialize_lineage(result) for result in lineage]
    reread_tags = sorted(str(tag.tag) for tag in tagged_field.tags)
    expected_tag = str(TagUrn(tag_name))
    path_text = json.dumps(serialized_lineage)
    lineage_passed = "payment_recorded_at" in path_text and "days_since_last_payment" in path_text
    tag_passed = expected_tag in reread_tags

    return {
        "schema_version": 1,
        "captured_at": datetime.now(UTC).isoformat(),
        "server": server,
        "status": "passed" if lineage_passed and tag_passed else "failed",
        "checks": {
            "dataset_upsert_and_reread": reread.urn == downstream.urn,
            "fine_grained_lineage_reread": lineage_passed,
            "colon_delimited_field_tag_reread": tag_passed,
        },
        "entities": {
            "upstream": str(upstream.urn),
            "downstream": str(downstream.urn),
        },
        "expected_tag": expected_tag,
        "reread_tags": reread_tags,
        "lineage": serialized_lineage,
    }


def _serialize_lineage(result: Any) -> dict[str, Any]:
    return {
        "urn": str(result.urn),
        "type": str(result.type),
        "hops": result.hops,
        "direction": result.direction,
        "paths": [
            {
                "urn": str(node.urn),
                "column_name": node.column_name,
                "entity_name": node.entity_name,
            }
            for node in result.paths
        ],
    }


def _get_lineage_with_retry(
    client: Any,
    source_urn: Any,
    *,
    source_column: str,
    attempts: int,
    delay_seconds: float,
) -> list[Any]:
    """Wait boundedly for DataHub's asynchronous lineage index."""
    for attempt in range(attempts):
        results = client.lineage.get_lineage(
            source_urn=source_urn,
            source_column=source_column,
            direction="upstream",
            max_hops=1,
        )
        if results:
            return results
        if attempt < attempts - 1:
            time.sleep(delay_seconds)
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default=os.getenv("DATAHUB_GMS_URL", "http://localhost:8080"))
    parser.add_argument("--token", default=os.getenv("DATAHUB_GMS_TOKEN"))
    parser.add_argument(
        "--output", type=Path, default=Path("evidence/phase0/datahub-roundtrip.local.json")
    )
    args = parser.parse_args()
    report = run_probe(args.server, args.token)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
