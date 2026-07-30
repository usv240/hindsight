"""Persist audit runs so the console has real history instead of one live result.

An audit is an event: it happened at a time, against a target, and reached a
verdict. Without persistence the console can only ever show "the audit", which is
why it read as a report rather than a product. Runs are written as one JSON file
each under ``evidence/runs/`` and indexed newest first.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath
from typing import Any

RUNS_DIRNAME = "evidence/runs"
_WINDOWS_ABSOLUTE = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\)")


def runs_dir(project_root: Path) -> Path:
    return Path(project_root) / RUNS_DIRNAME


def _portable_string(value: str, project_root: Path) -> str:
    """Remove host-specific prefixes from path-shaped evidence values."""
    if value.startswith(("http://", "https://", "urn:")):
        return value

    root = Path(project_root).resolve()
    if _WINDOWS_ABSOLUTE.match(value):
        candidate = PureWindowsPath(value)
        windows_root = PureWindowsPath(str(root))
        try:
            return candidate.relative_to(windows_root).as_posix()
        except ValueError:
            return f"<external>/{candidate.name}"

    candidate = Path(value)
    if candidate.is_absolute():
        try:
            return candidate.resolve().relative_to(root).as_posix()
        except ValueError:
            return f"<external>/{candidate.name}"
    return value


def portable_record(value: Any, project_root: Path) -> Any:
    """Return JSON-compatible evidence with no machine-specific absolute paths."""
    if isinstance(value, dict):
        return {key: portable_record(item, project_root) for key, item in value.items()}
    if isinstance(value, list):
        return [portable_record(item, project_root) for item in value]
    if isinstance(value, tuple):
        return [portable_record(item, project_root) for item in value]
    if isinstance(value, str):
        return _portable_string(value, project_root)
    return value


def _bundle_hash(bundle: dict[str, Any]) -> str:
    canonical = json.dumps(bundle, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def record_run(
    project_root: Path,
    bundle: dict[str, Any],
    *,
    publication: dict[str, Any] | None = None,
    scenario: str | None = None,
) -> dict[str, Any]:
    """Write a compact summary of one audit run and return it."""
    directory = runs_dir(project_root)
    directory.mkdir(parents=True, exist_ok=True)

    now = datetime.now(UTC)
    bundle = portable_record(bundle, project_root)
    publication = portable_record(publication, project_root)
    run = {
        "schema_version": 2,
        "run_id": f"{now.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}",
        "started_at": now.isoformat(),
        "audit": bundle.get("audit_config", {}).get("name", "unknown"),
        "scenario": scenario or bundle.get("audit_config", {}).get("name"),
        "case_id": bundle.get("case_id"),
        "verdict": bundle.get("verdict"),
        "release_decision": bundle.get("release_decision"),
        "exit_code": bundle.get("exit_code"),
        "runtime_seconds": bundle.get("validation", {}).get("runtime_seconds"),
        "rows": bundle.get("validation", {}).get("rows"),
        "target_urn": bundle.get("audit_config", {}).get("target_urn"),
        "published": bool(publication and publication.get("mutation_performed")),
        "evidence_sha256": _bundle_hash(bundle),
        "evidence_bundle": bundle,
        "publication": publication,
    }
    path = directory / f"{run['run_id']}.json"
    path.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    return run


def list_runs(project_root: Path, limit: int | None = 50) -> list[dict[str, Any]]:
    """Return recorded runs, newest first. Never raises on a bad file.

    ``limit=None`` reads every run. Aggregates need that: a summary computed
    from the newest 50 silently drops scenarios that have not run recently.
    """
    directory = runs_dir(project_root)
    if not directory.exists():
        return []

    runs: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json"), reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        # A file can be valid JSON and still not be a run: `null`, a list, a bare
        # number. Anything that is not an object would crash the templates, so
        # the type check has to come before any dict operation.
        if not isinstance(payload, dict):
            continue
        payload = portable_record(payload, project_root)
        payload.pop("evidence_bundle", None)
        payload.pop("publication", None)
        runs.append(payload)
        if limit is not None and len(runs) >= limit:
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
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    payload = portable_record(payload, project_root)
    bundle = payload.get("evidence_bundle")
    if isinstance(bundle, dict):
        payload["evidence_sha256"] = _bundle_hash(bundle)
    return payload


def group_by_scenario(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse run history into one row per scenario.

    Fifty near-identical rows is not history, it is noise. What a reviewer wants
    to know is: which scenarios have been audited, what did each conclude, and
    has any of them ever disagreed with itself.
    """
    groups: dict[str, dict[str, Any]] = {}
    for run in runs:
        key = run.get("scenario") or run.get("audit") or "unknown"
        group = groups.setdefault(
            key,
            {
                "scenario": key,
                "runs": [],
                "decisions": set(),
                "latest": run,
                "blocked": 0,
                "allowed": 0,
            },
        )
        group["runs"].append(run)
        decision = run.get("release_decision")
        group["decisions"].add(decision)
        if decision == "block":
            group["blocked"] += 1
        elif decision == "allow":
            group["allowed"] += 1

    result = []
    for group in groups.values():
        runtimes = [r["runtime_seconds"] for r in group["runs"] if r.get("runtime_seconds")]
        result.append(
            {
                "scenario": group["scenario"],
                "count": len(group["runs"]),
                "latest": group["latest"],
                "blocked": group["blocked"],
                "allowed": group["allowed"],
                # A scenario that has ever disagreed with itself is worth seeing.
                "consistent": len(group["decisions"]) == 1,
                "median_runtime": sorted(runtimes)[len(runtimes) // 2] if runtimes else None,
                "recent": group["runs"][:12],
            }
        )
    result.sort(key=lambda g: g["latest"].get("started_at", ""), reverse=True)
    return result
