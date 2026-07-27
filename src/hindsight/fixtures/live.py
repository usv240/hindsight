from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hindsight.fixtures.replay import run_fixture_replay
from hindsight.phase0.datahub_probe import _get_lineage_with_retry, _serialize_lineage


def verify_live_fixture(
    fixture_dir: Path,
    *,
    target_urn: str,
    server: str,
    token: str | None = None,
) -> dict[str, Any]:
    """Prove the sanitized fixture retains the semantics of a live DataHub asset."""
    offline = run_fixture_replay(fixture_dir)
    if offline["status"] != "passed":
        return {
            "schema_version": 1,
            "status": "fixture_integrity_failed",
            "offline": offline,
        }

    from datahub.metadata.urns import DatasetUrn, TagUrn
    from datahub.sdk import DataHubClient

    client = DataHubClient(server=server, token=token)
    client.test_connection()
    target = client.entities.get(target_urn)
    expected_entity = json.loads(
        (fixture_dir / "responses/entity.json").read_text(encoding="utf-8")
    )
    expected_lineage = json.loads(
        (fixture_dir / "responses/lineage.json").read_text(encoding="utf-8")
    )
    target_column = expected_lineage["target"]["column"]
    lineage = _get_lineage_with_retry(
        client,
        DatasetUrn.from_string(target_urn),
        source_column=target_column,
        attempts=10,
        delay_seconds=2,
    )
    serialized = [_serialize_lineage(result) for result in lineage]
    lineage_text = json.dumps(serialized)
    live_fields = {field.field_path: field for field in target.schema}
    expected_fields = {field["field_path"] for field in expected_entity["schema"]}
    live_tags = {str(association.tag) for association in live_fields[target_column].tags}
    checks = {
        "offline_fixture_replay_passed": True,
        "expected_schema_fields_present": expected_fields <= set(live_fields),
        "candidate_field_tag_present": str(TagUrn("hindsight:leakage-candidate")) in live_tags,
        "target_column_lineage_present": target_column in lineage_text,
        "upstream_column_lineage_present": (expected_lineage["source"]["column"] in lineage_text),
    }
    return {
        "schema_version": 1,
        "captured_at": datetime.now(UTC).isoformat(),
        "status": "passed" if all(checks.values()) else "failed",
        "server": server,
        "target_urn": target_urn,
        "fixture_id": offline["fixture_id"],
        "fixture_manifest_sha256": offline["manifest_sha256"],
        "checks": checks,
        "live_tags": sorted(live_tags),
        "live_lineage": serialized,
    }
