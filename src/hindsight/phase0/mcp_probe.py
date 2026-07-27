from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REQUIRED_TOOLS = {
    "search",
    "get_entities",
    "get_lineage",
    "add_tags",
    "add_structured_properties",
    "save_document",
}
TAG_NAME = "hindsight:mcp-verified"
TAG_URN = f"urn:li:tag:{TAG_NAME}"
TAG_DISPLAY_NAME = "Hindsight MCP verified"


async def run_probe(mcp_url: str, datahub_server: str) -> dict[str, Any]:
    """Prove real DataHub reads and an approved mutation through MCP."""
    from datahub.sdk import DataHubClient, Tag
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    datahub = DataHubClient(server=datahub_server)
    datahub.test_connection()
    datahub.entities.upsert(
        Tag(
            name=TAG_NAME,
            display_name=TAG_DISPLAY_NAME,
            description="Phase 0 proof of governed Hindsight MCP write-back.",
        )
    )

    async with streamable_http_client(mcp_url) as (read_stream, write_stream, _):  # noqa: SIM117
        async with ClientSession(read_stream, write_stream) as session:
            initialized = await session.initialize()
            listed = await session.list_tools()
            tool_names = {tool.name for tool in listed.tools}

            search = await session.call_tool(
                "search",
                {"query": "hindsight.phase0.leaky_features_*", "num_results": 20},
            )
            search_results = (search.structuredContent or {}).get("searchResults", [])
            if not search_results:
                raise RuntimeError("MCP search did not find a seeded Hindsight feature dataset")
            target_urn = search_results[-1]["entity"]["urn"]

            lineage = await session.call_tool(
                "get_lineage",
                {
                    "urn": target_urn,
                    "column": "days_since_last_payment",
                    "upstream": True,
                    "max_hops": 1,
                },
            )
            lineage_payload = lineage.structuredContent or {}
            lineage_text = json.dumps(lineage_payload)
            lineage_passed = not lineage.isError and "payment_recorded_at" in lineage_text

            mutation = await session.call_tool(
                "add_tags",
                {
                    "tag_urns": [TAG_URN],
                    "entity_urns": [target_urn],
                    "column_paths": ["days_since_last_payment"],
                },
            )
            reread = await session.call_tool("get_entities", {"urns": [target_urn]})
            reread_text = json.dumps(reread.structuredContent or {})
            mutation_passed = (
                not mutation.isError and not reread.isError and TAG_DISPLAY_NAME in reread_text
            )

    checks = {
        "required_tools_exposed": tool_names >= REQUIRED_TOOLS,
        "search_found_seeded_asset": bool(search_results),
        "column_lineage_read_through_mcp": lineage_passed,
        "field_tag_mutation_and_reread_through_mcp": mutation_passed,
    }
    return {
        "schema_version": 1,
        "captured_at": datetime.now(UTC).isoformat(),
        "mcp_url": mcp_url,
        "server": {
            "name": initialized.serverInfo.name,
            "version": initialized.serverInfo.version,
        },
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "target_urn": target_urn,
        "required_tools": sorted(REQUIRED_TOOLS),
        "available_tools": sorted(tool_names),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mcp-url", default="http://127.0.0.1:8000/mcp")
    parser.add_argument("--datahub-server", default="http://localhost:8080")
    parser.add_argument("--output", type=Path, default=Path("evidence/phase0/mcp.local.json"))
    args = parser.parse_args()
    report = asyncio.run(run_probe(args.mcp_url, args.datahub_server))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
