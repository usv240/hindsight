from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def refresh_fixture_hashes(fixture_dir: Path, *, approved: bool = False) -> dict[str, Any]:
    """Preview or explicitly refresh fixture hashes after an intentional recapture."""
    root = fixture_dir.resolve()
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    changes = []
    lines = []
    for item in manifest["files"]:
        path = root / item["path"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {item['path']}")
        if digest != item["sha256"]:
            changes.append(
                {
                    "path": item["path"],
                    "previous_sha256": item["sha256"],
                    "current_sha256": digest,
                }
            )
            item["sha256"] = digest

    if approved:
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        (root / "hashes.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "schema_version": 1,
        "fixture_id": manifest["fixture_id"],
        "status": "refreshed" if approved else "preview",
        "changes": changes,
        "mutation_performed": approved,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=Path("fixtures/credit_default"))
    parser.add_argument("--approve-refresh", action="store_true")
    args = parser.parse_args()
    report = refresh_fixture_hashes(args.fixture, approved=args.approve_refresh)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
