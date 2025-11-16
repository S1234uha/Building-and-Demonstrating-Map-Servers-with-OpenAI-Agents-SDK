from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI

from map_agents import MapAssistant, MapToolkit, OpenStreetMapServer, OSRMRoutingServer


async def main() -> None:
    load_dotenv()
    toolkit = MapToolkit(
        [
            OpenStreetMapServer(),
            OSRMRoutingServer(),
        ]
    )
    client = AsyncOpenAI()
    agent = MapAssistant(
        client=client,
        toolkit=toolkit,
        model=os.getenv("OPENAI_MODEL", "gpt-4o"),
    )
    await agent.bootstrap()
    print("Map assistant ready. Type 'quit' to stop.")
    try:
        while True:
            query = (await asyncio.to_thread(input, "map> ")).strip()
            if not query or query.lower() in {"quit", "exit"}:
                break
            response = await agent.ask(query)
            print(f"\n{response}\n")
    finally:
        await toolkit.aclose()


if __name__ == "__main__":
    asyncio.run(main())
