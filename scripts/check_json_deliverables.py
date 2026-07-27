"""Fail if any committed JSON deliverable carries a BOM or cannot be parsed.

Judges and downstream tooling may parse the evaluation pack, fixtures and
example cases directly. PowerShell redirection on Windows writes a UTF-8 BOM by
default, and ``json.load`` rejects it, so a file that looks correct in an editor
can be unusable to anyone else.
"""

from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SEARCH_DIRS = ("evaluations", "fixtures", "examples", "scenarios")
BOM = b"\xef\xbb\xbf"


def main() -> int:
    problems: list[str] = []
    checked = 0

    for directory in SEARCH_DIRS:
        for path in sorted((ROOT / directory).rglob("*.json")):
            if ".local." in path.name:
                continue
            checked += 1
            relative = path.relative_to(ROOT).as_posix()
            raw = path.read_bytes()
            if raw.startswith(BOM):
                problems.append(f"{relative}: starts with a UTF-8 BOM")
                continue
            try:
                json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                problems.append(f"{relative}: does not parse ({error})")

    if problems:
        print("JSON deliverable check FAILED:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print(f"JSON deliverable check passed: {checked} files are BOM-free and parse strictly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
