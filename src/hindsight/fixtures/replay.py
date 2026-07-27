from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from hindsight.detectors import verify_temporal_cutoff
from hindsight.engine import audit_case
from hindsight.models import AuditCase


def run_fixture_replay(fixture_dir: Path) -> dict[str, Any]:
    """Replay recorded metadata without DataHub, Docker, a warehouse, or an LLM."""
    started = time.perf_counter()
    root = fixture_dir.resolve()
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    integrity_errors = _integrity_errors(root, manifest)
    hashes_txt_matches = _hashes_txt_matches(root, manifest)
    if not hashes_txt_matches:
        integrity_errors.append("hashes.txt does not match manifest.json")
    if integrity_errors:
        return {
            "schema_version": 1,
            "fixture_id": manifest.get("fixture_id"),
            "status": "integrity_failed",
            "errors": integrity_errors,
            "external_services_used": [],
            "runtime_seconds": round(time.perf_counter() - started, 6),
            "exit_code": 2,
        }

    ground_truth = _read_json(root / "ground_truth.json")
    entity = _read_json(root / "responses/entity.json")
    lineage = _read_json(root / "responses/lineage.json")
    validation = _read_json(root / "responses/validation.json")
    transformation = verify_temporal_cutoff(
        (root / "transformation.sql").read_text(encoding="utf-8"),
        post_outcome_table="payment_events_after_decision",
    )
    remediation = verify_temporal_cutoff(
        (root / "remediation.sql").read_text(encoding="utf-8"),
        post_outcome_table="payment_events_after_decision",
    )

    leakage_result = audit_case(
        AuditCase.from_dict(
            {
                "case_id": ground_truth["case_id"],
                "model_urn": ground_truth["model_urn"],
                "feature_urn": ground_truth["feature_urn"],
                "lineage_path": lineage["path"],
                "source_kind": ground_truth["source_kind"],
                "source_available_at": ground_truth["source_available_at"],
                "prediction_time": ground_truth["prediction_time"],
                "point_in_time_advantage_collapsed": validation["leakage_case"]["collapsed"],
                "ablation_delta": validation["leakage_case"]["observed_advantage"],
            }
        )
    )
    safe_payload = dict(ground_truth["safe_control"])
    safe_payload.pop("expected_verdict")
    safe_payload["point_in_time_advantage_collapsed"] = validation["safe_control"]["collapsed"]
    safe_payload["ablation_delta"] = validation["safe_control"]["observed_advantage"]
    safe_result = audit_case(AuditCase.from_dict(safe_payload))
    release_decision = "block" if leakage_result.exit_code == 3 else "review"
    expected = manifest["expected"]
    tagged_field = next(
        field for field in entity["schema"] if field["field_path"] == lineage["target"]["column"]
    )
    checks = {
        "manifest_hashes_verified": True,
        "hashes_txt_matches_manifest": hashes_txt_matches,
        "recorded_field_tag_present": (
            "urn:li:tag:hindsight:leakage-candidate" in tagged_field["tags"]
        ),
        "lineage_direction_is_upstream": lineage["direction"] == "upstream",
        "leakage_verdict_matches_ground_truth": (
            leakage_result.verdict.value
            == ground_truth["expected_verdict"]
            == expected["leakage_verdict"]
        ),
        "safe_control_matches_ground_truth": (
            safe_result.verdict.value
            == ground_truth["safe_control"]["expected_verdict"]
            == expected["safe_control_verdict"]
        ),
        "release_decision_matches_ground_truth": (
            release_decision
            == ground_truth["expected_release_decision"]
            == expected["release_decision"]
        ),
        "transformation_violation_reproduced": (
            transformation.status == expected["transformation_status"]
        ),
        "remediation_safe_reproduced": remediation.status == expected["remediation_status"],
    }
    return {
        "schema_version": 1,
        "fixture_id": manifest["fixture_id"],
        "manifest_sha256": _sha256(manifest_path),
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "release_decision": release_decision,
        "verdicts": {
            "leakage_case": leakage_result.to_dict(),
            "safe_control": safe_result.to_dict(),
        },
        "sql": {
            "transformation": transformation.to_dict(),
            "remediation": remediation.to_dict(),
        },
        "recorded_validation": validation,
        "captured_from": manifest["captured_from"],
        "external_services_used": [],
        "runtime_seconds": round(time.perf_counter() - started, 6),
        "exit_code": 0 if all(checks.values()) else 2,
    }


def _integrity_errors(root: Path, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for item in manifest.get("files", []):
        relative = Path(item["path"])
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            errors.append(f"path escapes fixture root: {relative.as_posix()}")
            continue
        if not candidate.is_file():
            errors.append(f"missing file: {relative.as_posix()}")
            continue
        actual = _sha256(candidate)
        if actual != item["sha256"]:
            errors.append(
                f"sha256 mismatch for {relative.as_posix()}: "
                f"expected {item['sha256']}, got {actual}"
            )
    return errors


def _hashes_txt_matches(root: Path, manifest: dict[str, Any]) -> bool:
    recorded = {}
    for line in (root / "hashes.txt").read_text(encoding="utf-8").splitlines():
        digest, path = line.split(maxsplit=1)
        recorded[path.strip()] = digest
    expected = {item["path"]: item["sha256"] for item in manifest["files"]}
    return recorded == expected


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
