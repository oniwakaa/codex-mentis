"""Pitagora Model Context Protocol (MCP) Stdio / JSON-RPC Server."""

import json
import sys
from typing import Any

from pitagora.mcp.resources import (
    MCP_RESOURCES,
    handle_read_concept_resource,
    handle_read_journey_resource,
    handle_read_memory_stats_resource,
)
from pitagora.mcp.tools import MCP_TOOLS


class MCPServer:
    """Pitagora MCP Server implementing JSON-RPC 2.0 protocol."""

    def __init__(self):
        self.tools = MCP_TOOLS
        self.resources = MCP_RESOURCES

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "description": spec["description"],
                "inputSchema": spec["input_schema"],
            }
            for name, spec in self.tools.items()
        ]

    def list_resources(self) -> list[dict[str, Any]]:
        return [
            {
                "uri": uri,
                "name": spec["name"],
                "description": spec["description"],
            }
            for uri, spec in self.resources.items()
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in self.tools:
            return {"error": f"Unknown tool: {name}"}
        handler = self.tools[name]["handler"]
        return await handler(**arguments)

    async def read_resource(self, uri: str) -> dict[str, Any]:
        if uri.startswith("pitagora://concepts/"):
            concept = uri.replace("pitagora://concepts/", "")
            return await handle_read_concept_resource(concept)
        elif uri.startswith("pitagora://journeys/"):
            journey_id = uri.replace("pitagora://journeys/", "")
            return await handle_read_journey_resource(journey_id)
        elif uri == "pitagora://memory/stats":
            return await handle_read_memory_stats_resource()
        return {"error": f"Unknown resource URI: {uri}"}

    async def handle_request(self, req: dict[str, Any]) -> dict[str, Any]:
        method = req.get("method", "")
        req_id = req.get("id")
        params = req.get("params", {})

        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": self.list_tools()}}
        elif method == "tools/call":
            name = params.get("name", "")
            args = params.get("arguments", {})
            result = await self.call_tool(name, args)
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        elif method == "resources/list":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"resources": self.list_resources()}}
        elif method == "resources/read":
            uri = params.get("uri", "")
            result = await self.read_resource(uri)
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }


def run_mcp_server() -> None:
    """Run MCP server over stdio for CLI `pitagora mcp serve`."""
    import asyncio

    server = MCPServer()

    async def loop():
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
                resp = await server.handle_request(req)
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
            except Exception as e:
                err_resp = {"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}}
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()

    asyncio.run(loop())
