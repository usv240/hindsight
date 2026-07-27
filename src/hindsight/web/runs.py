"""Persist audit runs so the console has real history instead of one live result.

An audit is an event: it happened at a time, against a target, and reached a
verdict. Without persistence the console can only ever show "the audit", which is
why it read as a report rather than a product. Runs are written as one JSON file
each under ``evidence/runs/`` and indexed newest first.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RUNS_DIRNAME = "evidence/runs"


def runs_dir(project_root: Path) -> Path:
    return Path(project_root) / RUNS_DIRNAME


def record_run(
    project_root: Path,
    bundle: dict[str, Any],
    *,
    publication: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write a compact summary of one audit run and return it."""
    directory = runs_dir(project_root)
    directory.mkdir(parents=True, exist_ok=True)

    now = datetime.now(UTC)
    run = {
        "schema_version": 1,
        "run_id": f"{now.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}",
        "started_at": now.isoformat(),
        "audit": bundle.get("audit_config", {}).get("name", "unknown"),
        "case_id": bundle.get("case_id"),
        "verdict": bundle.get("verdict"),
        "release_decision": bundle.get("release_decision"),
        "exit_code": bundle.get("exit_code"),
        "runtime_seconds": bundle.get("validation", {}).get("runtime_seconds"),
        "rows": bundle.get("validation", {}).get("rows"),
        "target_urn": bundle.get("audit_config", {}).get("target_urn"),
        "published": bool(publication and publication.get("mutation_performed")),
    }
    path = directory / f"{run['run_id']}.json"
    path.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    return run


def list_runs(project_root: Path, limit: int = 50) -> list[dict[str, Any]]:
    """Return recorded runs, newest first. Never raises on a bad file."""
    directory = runs_dir(project_root)
    if not directory.exists():
        return []

    runs: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json"), reverse=True):
        try:
            runs.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
        if len(runs) >= limit:
            break
    return runs


def get_run(project_root: Path, run_id: str) -> dict[str, Any] | None:
    # Guard against traversal: run ids are generated, never user-authored.
    if not run_id.replace("-", "").isalnum():
        return None
    path = runs_dir(project_root) / f"{run_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
