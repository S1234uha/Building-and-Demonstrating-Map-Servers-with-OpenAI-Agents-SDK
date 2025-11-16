from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

from ..config import MapCommand, ServerMetadata


@dataclass(slots=True)
class MapServer:
    """Base class shared by all map servers."""

    metadata: ServerMetadata
    commands: List[MapCommand]

    def tool_specs(self) -> Iterable[Dict[str, Any]]:
        for command in self.commands:
            yield command.to_openai_tool()

    async def dispatch(self, name: str, *, arguments: Dict[str, Any]) -> Dict[str, Any]:
        for command in self.commands:
            if command.name == name:
                return await command.handler(**arguments)
        raise KeyError(f"Unknown command {name}")

    async def aclose(self) -> None:
        """Hook for cleaning up network clients."""
        return None

