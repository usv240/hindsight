"""Edge cases and hostile input, found by adversarial probing rather than design.

Each test here corresponds to a defect that a probe actually triggered. The SSRF
rules follow OWASP guidance: allowlist the scheme, validate the *resolved*
address rather than the string, and always refuse link-local and cloud metadata
ranges.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hindsight.netguard import EndpointError, validate_endpoint
from hindsight.web import create_app
from hindsight.web.runs import get_run, list_runs, runs_dir
from hindsight.web.timeline import build_timeline


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(Path.cwd()))


def _csrf(client: TestClient) -> str:
    page = client.get("/audits/latest", follow_redirects=True).text
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', page)
    assert match, "expected a CSRF token in the publish form"
    return match.group(1)


# -- SSRF -------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com",
        "gopher://example.com",
        "javascript:alert(1)",
        "dict://example.com",
        "//example.com",
        "",
        "   ",
    ],
)
def test_non_http_schemes_are_refused(url: str) -> None:
    with pytest.raises(EndpointError):
        validate_endpoint(url, resolve=False)


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",  # AWS/GCP/Azure IMDS
        "http://169.254.170.2/",  # ECS task metadata
        "https://169.254.169.254",
    ],
)
def test_cloud_metadata_endpoints_are_refused(url: str) -> None:
    """The canonical SSRF target: instance metadata returns credentials."""
    with pytest.raises(EndpointError, match="metadata"):
        validate_endpoint(url)


def test_the_documented_local_datahub_is_still_allowed() -> None:
    """Blocking loopback would break the documented DataHub Core setup."""
    endpoint = validate_endpoint("http://localhost:8080")
    assert endpoint.host == "localhost"
    assert endpoint.port == 8080


def test_a_malformed_port_is_refused() -> None:
    with pytest.raises(EndpointError):
        validate_endpoint("http://example.com:99999", resolve=False)


def test_unresolvable_hosts_do_not_crash() -> None:
    """DNS being down must not stop a page rendering; the call fails on its own."""
    endpoint = validate_endpoint("http://this-host-does-not-exist.invalid:8080")
    assert endpoint.resolved == ()


def test_console_refuses_to_publish_to_a_metadata_endpoint(client: TestClient) -> None:
    response = client.post(
        "/publish",
        data={
            "target_urn": "urn:li:dataset:x",
            "server": "http://169.254.169.254/latest/meta-data/",
            "csrf_token": _csrf(client),
        },
    )
    assert response.status_code == 200
    assert "metadata" in response.text.lower()
    assert "mutation_performed" not in response.text or "true" not in response.text.lower()


def test_console_refuses_a_file_scheme(client: TestClient) -> None:
    response = client.post(
        "/publish",
        data={
            "target_urn": "urn:li:dataset:x",
            "server": "file:///etc/passwd",
            "csrf_token": _csrf(client),
        },
    )
    assert response.status_code == 200
    assert "scheme" in response.text.lower()


# -- Timeline ---------------------------------------------------------------


@pytest.mark.parametrize(
    "prediction_time",
    [
        "0001-01-01T00:00:00Z",  # overflowed the window subtraction
        "9999-12-31T23:59:59Z",  # overflowed the window addition
        "1970-01-01T00:00:00Z",
        None,
        "",
        "not-a-date",
        12345,
    ],
)
def test_timeline_survives_degenerate_prediction_times(prediction_time: object) -> None:
    timeline = build_timeline({}, {"prediction_time": prediction_time})
    assert timeline.tracks
    for track in timeline.tracks:
        assert 0.0 <= track.start_pct <= 100.0
        assert 0.0 <= track.end_pct <= 100.0
        if track.crosses:
            assert track.reach_pct <= 100.0


@pytest.mark.parametrize("days", [0, -5, 10**6])
def test_timeline_keeps_absurd_violations_inside_the_frame(days: int) -> None:
    timeline = build_timeline(
        {"sql_verification": {"days_after": days}},
        {"prediction_time": "2026-01-10T09:00:00Z"},
    )
    for track in timeline.tracks:
        assert track.reach_pct <= 100.0


# -- Run files --------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("_t_broken.json", "{not json"),
        ("_t_empty.json", ""),
        ("_t_null.json", "null"),
        ("_t_list.json", "[1, 2, 3]"),
        ("_t_string.json", '"just a string"'),
        ("_t_number.json", "42"),
    ],
)
def test_a_corrupt_run_file_cannot_break_the_console(
    client: TestClient, name: str, content: str
) -> None:
    """Valid JSON that is not an object used to crash the run listing."""
    path = runs_dir(Path.cwd()) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    try:
        list_runs(Path.cwd())
        assert client.get("/audits").status_code == 200
        assert client.get("/").status_code == 200
        assert get_run(Path.cwd(), name.removesuffix(".json")) is None
    finally:
        path.unlink(missing_ok=True)


def test_a_run_file_missing_every_field_still_lists(client: TestClient) -> None:
    path = runs_dir(Path.cwd()) / "_t_sparse.json"
    path.write_text(json.dumps({"run_id": "_t_sparse"}), encoding="utf-8")
    try:
        assert client.get("/audits").status_code == 200
        assert client.get("/").status_code == 200
    finally:
        path.unlink(missing_ok=True)


# -- Injection --------------------------------------------------------------


def test_hostile_urn_is_escaped_not_reflected(client: TestClient) -> None:
    response = client.post(
        "/publish",
        data={
            "target_urn": "<script>alert(1)</script>",
            "server": "http://must-not-be-called.invalid",
            "csrf_token": _csrf(client),
        },
    )
    assert "<script>alert(1)</script>" not in response.text


def test_publish_requires_a_csrf_token(client: TestClient) -> None:
    response = client.post(
        "/publish",
        data={"target_urn": "urn:li:dataset:x", "server": "http://localhost:8080"},
    )
    assert response.status_code == 403
