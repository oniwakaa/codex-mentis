import pytest

from pitagora.mcp.server import MCPServer


@pytest.mark.asyncio
async def test_mcp_server_list_tools():
    server = MCPServer()
    tools = server.list_tools()
    assert len(tools) == 4
    tool_names = [t["name"] for t in tools]
    assert "pitagora_solve" in tool_names
    assert "pitagora_verify" in tool_names
    assert "pitagora_explain" in tool_names
    assert "pitagora_concept_status" in tool_names


@pytest.mark.asyncio
async def test_mcp_server_call_tools(temp_db):
    server = MCPServer()

    res_verify = await server.call_tool("pitagora_verify", {"expression": "2 + 2"})
    assert res_verify["verified"] is True
    assert "4" in str(res_verify["value"])

    res_explain = await server.call_tool(
        "pitagora_explain", {"topic": "Calculus", "level": "beginner"}
    )
    assert "Calculus" in res_explain["topic"]
    assert "explanation" in res_explain

    res_concept = await server.call_tool("pitagora_concept_status", {"concept": "Limits"})
    assert res_concept["concept"] == "Limits"


@pytest.mark.asyncio
async def test_mcp_server_list_and_read_resources(temp_db):
    server = MCPServer()
    resources = server.list_resources()
    assert len(resources) == 3

    res_concept = await server.read_resource("pitagora://concepts/Derivatives")
    assert res_concept["concept"] == "Derivatives"

    res_stats = await server.read_resource("pitagora://memory/stats")
    assert "total_memories" in res_stats


@pytest.mark.asyncio
async def test_mcp_server_json_rpc_handling():
    server = MCPServer()

    req_list = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    resp_list = await server.handle_request(req_list)
    assert resp_list["id"] == 1
    assert "tools" in resp_list["result"]

    req_call = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "pitagora_verify", "arguments": {"expression": "3 * 3"}},
    }
    resp_call = await server.handle_request(req_call)
    assert resp_call["id"] == 2
    assert resp_call["result"]["verified"] is True
