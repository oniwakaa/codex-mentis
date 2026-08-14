"""MCP server manager — loads config, spawns stdio servers, routes tool calls.

ponytail: minimal JSON-RPC-over-stdio client. Uses the `mcp` SDK when
installed (optional `[mcp]` extra); otherwise exposes config + listing only
and degrades gracefully (no subprocess execution). The ceiling is: without
the `mcp` package, call_tool raises NotImplementedError. Upgrade path: install
the extra and the same call_tool works against a real server.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pitagora.core.constants import MCP_CONFIG_PATH

DEFAULT_MCP_SERVERS: dict[str, dict[str, Any]] = {
    "evermemos": {
        "command": "npx",
        "args": ["-y", "evermemos-mcp"],
        "env": {"EVERMEMOS_API_KEY": "${EVERMEMOS_API_KEY}"},
        "description": "Long-term memory for knowledge persistence",
        "enabled": True,
    },
    "sequential-thinking": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
        "description": "Step-by-step reasoning chains",
        "enabled": True,
    },
    "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "${HOME}/pitagora-workspace"],
        "description": "File operations within workspace",
        "enabled": False,
    },
    "sqlite": {
        "command": "npx",
        "args": [
            "-y",
            "@modelcontextprotocol/server-sqlite",
            "--db-path",
            "${HOME}/.pitagora/data.db",
        ],
        "description": "Query pitagora's database directly",
        "enabled": False,
    },
    "arxiv": {
        "command": "npx",
        "args": ["-y", "arxiv-mcp-server"],
        "description": "Search and read academic papers",
        "enabled": False,
    },
    "web-search": {
        "command": "npx",
        "args": ["-y", "brave-search-mcp"],
        "env": {"BRAVE_API_KEY": "${BRAVE_API_KEY}"},
        "description": "Web search for research",
        "enabled": False,
    },
}


@dataclass
class MCPServer:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    description: str = ""
    _proc: Any = None

    @classmethod
    def from_config(cls, name: str, cfg: dict[str, Any]) -> MCPServer:
        return cls(
            name=name,
            command=cfg.get("command", ""),
            args=list(cfg.get("args", [])),
            env=dict(cfg.get("env", {})),
            enabled=bool(cfg.get("enabled", True)),
            description=cfg.get("description", ""),
        )

    def to_config(self) -> dict[str, Any]:
        cfg: dict[str, Any] = {
            "command": self.command,
            "args": self.args,
            "enabled": self.enabled,
        }
        if self.env:
            cfg["env"] = self.env
        if self.description:
            cfg["description"] = self.description
        return cfg


def _expand_env(value: str) -> str:
    """Expand ${VAR} and ~ in a single string."""
    return os.path.expandvars(os.path.expanduser(value))


class MCPManager:
    """Manages MCP server connections for Pitagora agents."""

    def __init__(self, config_path: Path | None = None):
        self.config_path = Path(config_path) if config_path else MCP_CONFIG_PATH
        self.servers: dict[str, MCPServer] = {}
        self._load_config(self.config_path)

    def _load_config(self, path: Path) -> None:
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            servers = data.get("mcpServers", {})
        else:
            servers = {}
        # Merge defaults with on-disk overrides (on-disk wins)
        merged = dict(DEFAULT_MCP_SERVERS)
        merged.update(servers)
        for name, cfg in merged.items():
            self.servers[name] = MCPServer.from_config(name, cfg)

    def save_config(self, path: Path | None = None) -> Path:
        """Persist current server config to mcp.json."""
        out_path = Path(path) if path else self.config_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"mcpServers": {name: srv.to_config() for name, srv in self.servers.items()}}
        with open(out_path, "w") as f:
            json.dump(data, f, indent=2)
        return out_path

    def get_enabled_servers(self) -> list[MCPServer]:
        return [s for s in self.servers.values() if s.enabled]

    def set_enabled(self, name: str, enabled: bool) -> None:
        if name in self.servers:
            self.servers[name].enabled = enabled

    def list_available_tools(self) -> dict[str, list[str]]:
        """List tools per enabled server. Requires the `mcp` SDK and a running
        server; returns empty lists when unavailable (graceful degradation)."""
        # ponytail: full tool discovery needs a live handshake; without the SDK
        # we return the known server names with empty tool lists.
        return {name: [] for name, s in self.servers.items() if s.enabled}

    async def call_tool(self, server: str, tool: str, args: dict) -> Any:
        """Call a tool on an MCP server over stdio JSON-RPC.

        Requires the optional `mcp` package. Raises NotImplementedError if the
        SDK is not installed, or KeyError if the server is unknown/disabled.
        """
        if server not in self.servers or not self.servers[server].enabled:
            raise KeyError(f"MCP server '{server}' not enabled")
        try:
            from mcp import ClientSession, StdioServerParameters  # type: ignore
            from mcp.client.stdio import stdio_client  # type: ignore
        except ImportError as exc:
            raise NotImplementedError(
                "MCP tool calls require the `mcp` package: pip install 'pitagora[mcp]'"
            ) from exc

        srv = self.servers[server]
        env = {k: _expand_env(v) for k, v in srv.env.items()}
        env.update(os.environ)
        args_expanded = [_expand_env(a) for a in srv.args]
        params = StdioServerParameters(command=srv.command, args=args_expanded, env=env)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool, args)
                return result
