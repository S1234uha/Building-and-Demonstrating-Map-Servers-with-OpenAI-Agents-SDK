from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Sequence

from openai.types.beta.threads.required_action_function_tool_call import (
    RequiredActionFunctionToolCall,
)

from .servers.base import MapServer


class MapToolkit:
    """Aggregates map servers and exposes MCP-style tools to OpenAI assistants."""

    def __init__(self, servers: Sequence[MapServer]) -> None:
        self._servers = list(servers)
        self._command_lookup: Dict[str, MapServer] = {}
        for server in self._servers:
            for command in server.commands:
                if command.name in self._command_lookup:
                    raise ValueError(f"duplicate command name {command.name}")
                self._command_lookup[command.name] = server

    @property
    def tool_specs(self) -> List[Dict[str, Any]]:
        specs: List[Dict[str, Any]] = []
        for server in self._servers:
            specs.extend(server.tool_specs())
        return specs

    async def invoke(self, tool_call: RequiredActionFunctionToolCall) -> Dict[str, Any]:
        arguments = json.loads(tool_call.function.arguments or "{}")
        server = self._command_lookup.get(tool_call.function.name)
        if not server:
            raise KeyError(f"Unknown tool {tool_call.function.name}")
        return await server.dispatch(tool_call.function.name, arguments=arguments)

    async def aclose(self) -> None:
        for server in self._servers:
            await server.aclose()

