from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str
    required: bool = True


def run_preflight() -> dict[str, object]:
    checks = [
        Check("python_3_11_plus", sys.version_info >= (3, 11), platform.python_version()),
        _command_check("uv", ["uv", "--version"]),
        _command_check("docker_client", ["docker", "--version"]),
        _docker_engine_check(),
        _docker_memory_check(),
        _wsl2_check(),
        _command_check("datahub_cli", ["datahub", "version"]),
    ]
    required_failures = [check.name for check in checks if check.required and not check.passed]
    return {
        "schema_version": 1,
        "captured_at": datetime.now(UTC).isoformat(),
        "status": "ready" if not required_failures else "blocked",
        "required_failures": required_failures,
        "checks": [asdict(check) for check in checks],
    }


def write_preflight(path: Path) -> dict[str, object]:
    report = run_preflight()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _command_check(name: str, command: list[str]) -> Check:
    if shutil.which(command[0]) is None:
        return Check(name, False, f"{command[0]} is not installed or not on PATH")
    completed = _run(command)
    detail = (completed.stdout or completed.stderr).strip()
    return Check(name, completed.returncode == 0, detail or f"exit={completed.returncode}")


def _docker_engine_check() -> Check:
    completed = _run(["docker", "info", "--format", "{{.ServerVersion}}"])
    detail = (completed.stdout or completed.stderr).strip()
    return Check("docker_engine", completed.returncode == 0, detail or "Docker engine unavailable")


def _docker_memory_check() -> Check:
    completed = _run(["docker", "info", "--format", "{{.MemTotal}}"])
    if completed.returncode != 0:
        return Check("docker_memory_8gb", False, "Cannot inspect memory until Docker engine runs")
    try:
        memory_bytes = int(completed.stdout.strip())
    except ValueError:
        return Check("docker_memory_8gb", False, f"Unexpected value: {completed.stdout.strip()}")
    gib = memory_bytes / (1024**3)
    return Check("docker_memory_8gb", gib >= 8, f"{gib:.2f} GiB allocated")


def _wsl2_check() -> Check:
    if platform.system() != "Windows":
        return Check("wsl2", True, "Not required on non-Windows host", required=False)
    completed = _run(["wsl", "--status"])
    detail = (completed.stdout or completed.stderr).replace("\x00", "").strip()
    passed = completed.returncode == 0 and "Default Version: 2" in detail
    return Check("wsl2", passed, detail or "WSL status unavailable")


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(command, 127, "", str(exc))
