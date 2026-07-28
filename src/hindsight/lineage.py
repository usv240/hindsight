"""Resolve the evidence path through DataHub's Agent Context Kit.

Hindsight's central question is a column-level, directional one: *is there a path
from this post-outcome column into this model feature?* Until now that path was
reconstructed by hand from a general lineage walk.

The Agent Context Kit ships exactly that primitive:

    get_lineage_paths_between(source_urn, target_urn,
                              source_column=..., target_column=...)

which is the operation, not an approximation of it. Using it means the evidence
path shown to a reviewer is **queried from the catalog** rather than assembled by
this codebase - a meaningful difference when the whole claim is "here is what the
graph says".

The Kit is an optional dependency. Everything degrades to `available=False` with
a stated reason rather than raising, because the offline judge path must keep
working with no DataHub, no network and no extra install.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PathResolution:
    """What the catalog says about a column-to-column path."""

    available: bool
    reason: str = ""
    found: bool = False
    hops: int = 0
    path: list[str] = field(default_factory=list)
    raw: dict[str, Any] | None = None
    source: str = "agent_context_kit"

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "reason": self.reason,
            "found": self.found,
            "hops": self.hops,
            "path": self.path,
            "resolved_by": self.source,
        }


def kit_available() -> tuple[bool, str]:
    """Whether the Agent Context Kit can be used right now."""
    try:
        import datahub_agent_context  # noqa: F401
    except ImportError:
        return False, "datahub-agent-context is not installed (install the 'datahub' extra)"
    if not os.getenv("DATAHUB_GMS_URL"):
        return False, "DATAHUB_GMS_URL is not set"
    return True, ""


def resolve_column_path(
    *,
    source_urn: str,
    source_column: str,
    target_urn: str,
    target_column: str,
) -> PathResolution:
    """Ask DataHub for the directional column path between two assets.

    A resolution of ``found=False`` is a real answer - it means the catalog knows
    of no path, which is evidence *against* leakage - and is distinct from
    ``available=False``, which means we never got to ask.
    """
    ok, reason = kit_available()
    if not ok:
        return PathResolution(available=False, reason=reason)

    try:
        from datahub.sdk import DataHubClient
        from datahub_agent_context import DataHubContext, mcp_tools

        # The Kit's tools read their client from a context variable, so the
        # connection has to be established around the call rather than passed in.
        client = DataHubClient(
            server=os.environ["DATAHUB_GMS_URL"],
            token=os.getenv("DATAHUB_GMS_TOKEN"),
        )
        with DataHubContext(client):
            payload = mcp_tools.get_lineage_paths_between(
                source_urn,
                target_urn,
                source_column=source_column,
                target_column=target_column,
                direction="downstream",
            )
    except Exception as error:  # noqa: BLE001
        # "No path exists" is an answer, and an important one: it is evidence
        # *against* leakage. Reporting it as "could not ask" would let a real
        # negative masquerade as an unknown - the same conflation this tool
        # refuses everywhere else.
        if _is_no_path(error):
            return PathResolution(
                available=True,
                found=False,
                reason="the catalog reports no path between these columns",
            )
        return PathResolution(available=False, reason=f"{type(error).__name__}: {error}")

    path = _extract_path(payload)
    return PathResolution(
        available=True,
        found=bool(path),
        hops=max(len(path) - 1, 0),
        path=path,
        raw=payload if isinstance(payload, dict) else None,
    )


def _is_no_path(error: Exception) -> bool:
    """Distinguish "the catalog says no" from "we could not reach the catalog"."""
    name = type(error).__name__
    message = str(error).lower()
    return name in {"ItemNotFoundError", "NotFoundError"} or "no lineage path found" in message


def _extract_path(payload: Any) -> list[str]:
    """Pull a readable hop list out of the Kit's response.

    The response shape is not part of a stable contract, so this reads
    defensively and returns an empty path rather than guessing.
    """
    if not isinstance(payload, dict):
        return []

    for key in ("paths", "lineage_paths", "results"):
        candidate = payload.get(key)
        if isinstance(candidate, list) and candidate:
            first = candidate[0]
            if isinstance(first, list):
                return [_label(hop) for hop in first]
            if isinstance(first, dict):
                for inner in ("path", "hops", "entities"):
                    hops = first.get(inner)
                    if isinstance(hops, list):
                        return [_label(hop) for hop in hops]
    return []


def _label(hop: Any) -> str:
    if isinstance(hop, str):
        return hop
    if isinstance(hop, dict):
        for key in ("column", "fieldPath", "urn", "name", "entity"):
            value = hop.get(key)
            if isinstance(value, str):
                return value
    return str(hop)
