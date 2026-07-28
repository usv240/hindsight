"""Report the real state of the DataHub connection.

The console used to render a hardcoded "DataHub evidence connected" pill with a
pulsing green dot. It said that whether or not DataHub was reachable, which is
exactly the kind of unevidenced assertion this project exists to catch. This
module actually checks, and distinguishes "not configured" from "unreachable" so
the UI can say something true in both cases.
"""

from __future__ import annotations

import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Literal

State = Literal["connected", "degraded", "offline", "not_configured"]

_CACHE_SECONDS = 10.0
_TIMEOUT_SECONDS = 2.0


@dataclass
class _Cached:
    target: str | None = None
    checked_at: float = 0.0
    payload: dict[str, Any] = field(default_factory=dict)


_cache = _Cached()


def datahub_health(server: str | None = None, *, force: bool = False) -> dict[str, Any]:
    """Return the current DataHub connection state.

    Cached briefly so a page with several components asking does not produce a
    burst of requests against the metadata service.
    """
    target = server or os.getenv("DATAHUB_GMS_URL")
    now = time.monotonic()
    if (
        not force
        and _cache.target == target
        and _cache.payload
        and (now - _cache.checked_at) < _CACHE_SECONDS
    ):
        return _cache.payload

    payload = _probe(target)
    _cache.target = target
    _cache.checked_at = now
    _cache.payload = payload
    return payload


def _probe(target: str | None) -> dict[str, Any]:
    if not target:
        return _result(
            "not_configured",
            "DataHub not configured",
            detail="Set DATAHUB_GMS_URL to connect. The console runs on recorded metadata.",
            server=None,
        )

    url = target.rstrip("/") + "/health"
    started = time.perf_counter()
    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            if 200 <= response.status < 300:
                return _result(
                    "connected",
                    "DataHub connected",
                    detail=f"{target} responded in {elapsed_ms} ms",
                    server=target,
                    latency_ms=elapsed_ms,
                )
            return _result(
                "degraded",
                "DataHub degraded",
                detail=f"{target} returned HTTP {response.status}",
                server=target,
                latency_ms=elapsed_ms,
            )
    except urllib.error.HTTPError as error:
        return _result(
            "degraded",
            "DataHub degraded",
            detail=f"{target} returned HTTP {error.code}",
            server=target,
        )
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return _result(
            "offline",
            "DataHub unreachable",
            detail=f"Could not reach {target}: {getattr(error, 'reason', error)}",
            server=target,
        )


def _result(
    state: State,
    label: str,
    *,
    detail: str,
    server: str | None,
    latency_ms: float | None = None,
) -> dict[str, Any]:
    return {
        "state": state,
        "label": label,
        "detail": detail,
        "server": server,
        "latency_ms": latency_ms,
        "can_write": state == "connected",
    }


def reset_cache() -> None:
    """Test hook - drop the cached probe result."""
    _cache.target = None
    _cache.checked_at = 0.0
    _cache.payload = {}
