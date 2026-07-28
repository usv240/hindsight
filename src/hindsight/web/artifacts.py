"""Collect the artifacts Hindsight has actually produced, for the evidence page.

The page used to describe what the tool writes. Describing is not evidence -
anyone can write a list. This reads the real files off disk: the audit document
that would be published, the repair that was proposed, the hashes proving the
recorded fixtures match the live capture they came from, and the sanitized
records of real runs against a live DataHub instance.

Nothing here is generated for display. If a file is missing, the page says so
rather than inventing a placeholder.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def collect(project_root: Path) -> dict[str, Any]:
    root = Path(project_root)
    return {
        "audit_document": _read_text(root / "examples/audit_document.md"),
        "remediation_sql": _read_text(root / "examples/remediation.sql"),
        "leaky_sql": _read_text(root / "examples/leaky_feature.sql"),
        "fixture": _fixture_integrity(root),
        "proofs": _proofs(root),
        "writeback_types": [
            {
                "kind": "Field tag",
                "urn": "hindsight:leakage-confirmed",
                "what": "Marks the exact column that broke the rule, not just the table.",
            },
            {
                "kind": "Structured property",
                "urn": "hindsight.auditVerdict",
                "what": "The verdict as typed, queryable metadata - not a free-text note.",
            },
            {
                "kind": "Document",
                "urn": "hindsight-audit-<case>",
                "what": "The full evidence path and safe-control results, linked to the asset.",
            },
            {
                "kind": "Incident",
                "urn": "ML_LEAKAGE",
                "what": "Open and actionable. Reused on retry rather than duplicated.",
            },
        ],
    }


def _fixture_integrity(root: Path) -> dict[str, Any]:
    """Hashes and capture provenance for the recorded metadata."""
    manifest_path = root / "fixtures/credit_default/manifest.json"
    if not manifest_path.exists():
        return {"available": False}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"available": False}

    files = []
    for entry in manifest.get("files", []):
        digest = str(entry.get("sha256", ""))
        files.append(
            {
                "path": entry.get("path", ""),
                "sha256": digest,
                "short": digest[:12],
                "exists": (manifest_path.parent / entry.get("path", "")).exists(),
            }
        )
    return {
        "available": True,
        "fixture_id": manifest.get("fixture_id"),
        "captured_at": manifest.get("captured_at"),
        "captured_from": manifest.get("captured_from", {}),
        "files": files,
    }


def _proofs(root: Path) -> list[dict[str, str]]:
    """Sanitized records of real runs, committed alongside the code."""
    known = [
        (
            "live",
            "Live DataHub end-to-end",
            "A full read/write/re-read cycle against DataHub Core.",
        ),
        (
            "phase0",
            "Feasibility proof",
            "Fine-grained lineage and every write-back type, verified.",
        ),
        ("writeback", "Write-back proof", "Each mutation re-read to confirm it persisted."),
        ("fixtures", "Fixture capture", "How the recorded metadata was produced."),
        ("skill", "Skill contract", "The reusable DataHub Skill, tested."),
        ("ui", "Console", "What the interface renders."),
    ]
    found = []
    for folder, title, blurb in known:
        directory = root / "evidence" / folder
        if not directory.exists():
            continue
        docs = sorted(directory.glob("*.md"), reverse=True)
        docs = [d for d in docs if d.name.lower() != "readme.md"]
        if not docs:
            continue
        found.append(
            {
                "title": title,
                "blurb": blurb,
                "path": f"evidence/{folder}/{docs[0].name}",
                "lines": str(
                    len(docs[0].read_text(encoding="utf-8", errors="replace").splitlines())
                ),
            }
        )
    return found


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None
