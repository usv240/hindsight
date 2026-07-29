"""The evidence record has to be takeable, not just viewable.

The page argues from the bundle; anyone doubting the argument should be able to
download it and check, rather than trust the rendering.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from hindsight.web.app import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _client() -> TestClient:
    return TestClient(create_app(PROJECT_ROOT))


def _a_run_id(client: TestClient) -> str:
    runs = client.get("/api/runs").json()["runs"]
    assert runs, "seeded runs should be committed"
    return runs[0]["run_id"]


def test_evidence_downloads_as_a_named_json_file() -> None:
    client = _client()
    run_id = _a_run_id(client)
    response = client.get(f"/audits/{run_id}/evidence.json")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert f'filename="hindsight-{run_id}.json"' in response.headers["content-disposition"]

    payload = json.loads(response.text)
    assert payload["run_id"] == run_id
    # The full record, not the trimmed one the list view serves.
    assert "evidence_bundle" in payload


def test_a_missing_run_is_404_not_an_empty_file() -> None:
    assert _client().get("/audits/nope/evidence.json").status_code == 404


def test_traversal_in_the_run_id_is_refused() -> None:
    """run ids are generated, so anything path-shaped is hostile."""
    for hostile in ("../../pyproject.toml", "..%2F..%2Fpyproject.toml"):
        assert _client().get(f"/audits/{hostile}/evidence.json").status_code in (404, 400)
