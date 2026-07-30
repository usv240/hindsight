"""Everything the console reads at runtime must reach the deployed image.

This exists because the same mistake shipped three times, and each time it was
invisible rather than loud:

  * the seeded runs were excluded by .gitignore, which `railway up` respects, so
    the hosted demo came up with zero audits and every scenario card linked to
    nothing;
  * `evaluations/` was never copied by the Dockerfile, so the benchmark chart -
    the project's strongest measurement - silently hid itself in production
    because the template guards on the file existing.

Graceful degradation is right for a missing optional file and wrong as the only
thing standing between a deploy and an empty page. These tests make the failure
loud at build time instead.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = PROJECT_ROOT / "Dockerfile"

# Directories the web app reads while serving a request. If the console needs it
# at runtime, the image needs it at build time.
RUNTIME_DIRECTORIES = (
    "evidence",
    "fixtures",
    "audits",
    "scenarios",
    "examples",
    "evaluations",
)


@pytest.fixture(scope="module")
def dockerfile() -> str:
    return DOCKERFILE.read_text(encoding="utf-8")


def test_the_image_copies_every_directory_the_console_reads(dockerfile: str) -> None:
    copied = set(re.findall(r"^COPY[^\n]*?\s(\S+)\s+\./\S+$", dockerfile, re.M))
    missing = [name for name in RUNTIME_DIRECTORIES if name not in copied]
    assert not missing, f"Dockerfile does not copy: {missing}"


def test_those_directories_actually_exist(dockerfile: str) -> None:
    for name in RUNTIME_DIRECTORIES:
        assert (PROJECT_ROOT / name).is_dir(), name


def test_nothing_the_image_needs_is_hidden_by_gitignore() -> None:
    """`railway up` builds its upload archive by respecting .gitignore.

    So an ignored file never reaches the build context and .dockerignore never
    gets a say. Anything the image copies must be visible to git.
    """
    import subprocess

    for name in RUNTIME_DIRECTORIES:
        tracked = subprocess.run(
            ["git", "ls-files", name],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.split()
        assert tracked, f"{name}/ has no tracked files; it will not reach the deploy"


def test_the_benchmark_the_chart_needs_is_tracked() -> None:
    """The chart hides itself when this file is absent, so absence must fail here."""
    import subprocess

    tracked = subprocess.run(
        ["git", "ls-files", "evaluations/benchmark.json"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    assert tracked, "evaluations/benchmark.json must be committed"


def test_raw_machine_reports_stay_out_of_the_image() -> None:
    """*.local.json are unsanitised local runs, not deliverables.

    The pattern needs the ** prefix: a bare *.local.json in .dockerignore only
    matches the root, so nested reports were still being copied.
    """
    ignore = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "**/*.local.json" in ignore


def test_the_start_command_is_defined_once() -> None:
    """railway.json used to repeat it, and the copy drifted.

    Its `$PORT` was not shell-expanded, so the container failed to start with
    "'$PORT' is not a valid integer" while the Dockerfile's own CMD was correct.
    """
    railway = (PROJECT_ROOT / "railway.json").read_text(encoding="utf-8")
    assert "startCommand" not in railway, "the Dockerfile CMD is the single definition"
    assert "uvicorn" in DOCKERFILE.read_text(encoding="utf-8")
