"""
Generic reusable MCP stdio client — connects to any MCP server subprocess.
"""

import json
import sys
import os
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClient:
    def __init__(self, server_script: str, env: dict = None):
        self._server_script = Path(server_script).resolve()
        self._env = {**os.environ, **(env or {})}
        self._stack: Optional[AsyncExitStack] = None
        self._session: Optional[ClientSession] = None

    async def start(self):
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(self._server_script)],
            env=self._env,
        )
        self._stack = AsyncExitStack()
        try:
            r, w = await self._stack.enter_async_context(stdio_client(params))
            self._session = await self._stack.enter_async_context(ClientSession(r, w))
            await self._session.initialize()
        except Exception:
            await self._stack.aclose()
            self._stack = None
            raise

    async def stop(self):
        if self._stack:
            await self._stack.aclose()
            self._stack = None
            self._session = None

    async def call(self, tool: str, args: dict[str, Any] = None) -> dict:
        result = await self._session.call_tool(tool, args or {})
        if result.content and result.content[0].type == "text":
            return json.loads(result.content[0].text)
        return {}
