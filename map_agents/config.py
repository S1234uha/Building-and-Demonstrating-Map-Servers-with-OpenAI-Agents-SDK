from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Mapping

ToolResult = Mapping[str, Any]
ToolHandler = Callable[..., Awaitable[ToolResult]]


@dataclass(slots=True)
class MapCommand:
    """Represents a single MCP-style command exposed by a map server."""

    name: str
    description: str
    parameters_schema: Dict[str, Any]
    handler: ToolHandler
    server: str

    def to_openai_tool(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }


@dataclass(slots=True)
class ServerMetadata:
    server_id: str
    summary: str
    provider: str
    docs_url: str | None = None
    attribution: str | None = None
    tags: list[str] = field(default_factory=list)

