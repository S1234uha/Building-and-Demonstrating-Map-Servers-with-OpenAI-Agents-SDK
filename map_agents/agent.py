from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Sequence

from openai import AsyncOpenAI
from openai.types.beta.assistant import Assistant
from openai.types.beta.threads import Message
from openai.types.beta.threads.run import Run

from .toolkit import MapToolkit


class MapAssistant:
    """
    Helper that wires MapToolkit commands into an OpenAI Assistant run loop.

    The class transparently handles tool calling via the Assistants API by
    submitting outputs whenever the run asks for additional actions.
    """

    def __init__(
        self,
        client: AsyncOpenAI,
        toolkit: MapToolkit,
        *,
        model: str,
        instructions: str | None = None,
        polling_interval: float = 1.0,
    ) -> None:
        self._client = client
        self._toolkit = toolkit
        self._model = model
        self._instructions = instructions or (
            "You are a helpful geospatial assistant. You must prefer calling the "
            "provided tools instead of guessing coordinates."
        )
        self._assistant: Assistant | None = None
        self._thread_id: str | None = None
        self._polling_interval = polling_interval

    async def bootstrap(self) -> None:
        """Creates the assistant and backing thread."""
        self._assistant = await self._client.beta.assistants.create(
            name="Map Servers Assistant",
            instructions=self._instructions,
            model=self._model,
            tools=self._toolkit.tool_specs,
        )
        thread = await self._client.beta.threads.create()
        self._thread_id = thread.id

    async def ask(self, prompt: str) -> str:
        if not self._assistant or not self._thread_id:
            raise RuntimeError("Call bootstrap() before starting a chat.")
        await self._client.beta.threads.messages.create(
            thread_id=self._thread_id,
            role="user",
            content=prompt,
        )
        run = await self._client.beta.threads.runs.create(
            thread_id=self._thread_id,
            assistant_id=self._assistant.id,
        )
        try:
            completed_run = await self._resolve_run(run)
        except RuntimeError as exc:
            return f"(Assistant run failed: {exc})"
        messages = await self._client.beta.threads.messages.list(
            thread_id=self._thread_id,
            order="desc",
            limit=1,
        )
        latest: Sequence[Message] = messages.data
        if not latest:
            return "No response produced."
        chunks: List[str] = []
        for block in latest[0].content:
            if block.type == "text":
                chunks.append(block.text.value)
        if not chunks:
            return f"(Run {completed_run.id} completed without text output.)"
        return "\n".join(chunks)

    async def _resolve_run(self, run: Run) -> Run:
        assert self._thread_id
        current = run
        while True:
            if current.status in {"queued", "in_progress"}:
                await asyncio.sleep(self._polling_interval)
                current = await self._client.beta.threads.runs.retrieve(
                    thread_id=self._thread_id,
                    run_id=current.id,
                )
                continue
            if current.status == "requires_action":
                tool_calls = current.required_action.submit_tool_outputs.tool_calls  # type: ignore[union-attr]
                tool_outputs = []
                for call in tool_calls:
                    result = await self._toolkit.invoke(call)
                    tool_outputs.append({"tool_call_id": call.id, "output": json.dumps(result)})
                current = await self._client.beta.threads.runs.submit_tool_outputs(
                    thread_id=self._thread_id,
                    run_id=current.id,
                    tool_outputs=tool_outputs,
                )
                continue
            if current.status == "completed":
                return current
            if current.status == "failed":
                detail = ""
                if getattr(current, "last_error", None):
                    err = current.last_error
                    detail = f" code={getattr(err, 'code', 'unknown')} message={getattr(err, 'message', '')}"
                raise RuntimeError(f"Run failed with status '{current.status}'.{detail}")
            raise RuntimeError(f"Run failed with status '{current.status}'")
