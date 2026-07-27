"""Fail if anything Hindsight prints to a console contains non-ASCII characters.

Windows consoles default to CP1252. A UTF-8 character written to stdout there
renders as a replacement character, so a judge running the golden demo would
see corrupted output in the first line of the project. This check guards the
console path only: HTML and JS are served as ``text/html; charset=utf-8`` with a
matching meta charset, so typography there is intentional and unaffected.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONSOLE_SOURCES = ("src/hindsight/demo.py", "src/hindsight/cli.py")


def scan_sources() -> list[str]:
    problems: list[str] = []
    for relative in CONSOLE_SOURCES:
        path = ROOT / relative
        if not path.exists():
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            offenders = sorted({hex(ord(char)) for char in line if ord(char) > 127})
            if offenders:
                problems.append(f"{relative}:{number}: non-ASCII {offenders}")
    return problems


def scan_rendered_demo() -> list[str]:
    result = subprocess.run(
        [sys.executable, "-m", "hindsight.cli", "demo"],
        capture_output=True,
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        return [f"demo exited {result.returncode}: {result.stderr.decode('utf-8', 'replace')}"]
    try:
        result.stdout.decode("ascii")
    except UnicodeDecodeError as error:
        return [f"rendered demo output is not ASCII: {error}"]
    return []


def main() -> int:
    problems = scan_sources() + scan_rendered_demo()
    if problems:
        print("ASCII console check FAILED:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print("ASCII console check passed: sources and rendered demo output are ASCII-only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
