from hindsight.phase0.preflight import run_preflight


def test_preflight_is_machine_readable_and_honest() -> None:
    report = run_preflight()
    assert report["schema_version"] == 1
    assert report["status"] in {"ready", "blocked"}
    checks = {check["name"]: check for check in report["checks"]}
    assert checks["python_3_11_plus"]["passed"] is True
    assert {"docker_engine", "docker_memory_8gb", "wsl2", "datahub_cli"} <= checks.keys()
