from __future__ import annotations

import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from openai import AsyncOpenAI

from map_agents import MapAssistant, MapToolkit, OpenStreetMapServer, OSRMRoutingServer

app = FastAPI(title="Map Assistant Chatbot")


@app.on_event("startup")
async def startup() -> None:
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
    app.state.agent = agent
    app.state.toolkit = toolkit


@app.on_event("shutdown")
async def shutdown() -> None:
    toolkit: MapToolkit = app.state.toolkit
    await toolkit.aclose()


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return """
    <!doctype html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Map Assistant Chatbot</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 720px; margin: 2rem auto; }
            #log { border: 1px solid #ccc; padding: 1rem; height: 400px; overflow-y: auto; white-space: pre-wrap; }
            textarea { width: 100%; height: 80px; }
            button { margin-top: 0.5rem; }
        </style>
    </head>
    <body>
        <h1>Map Assistant Chatbot</h1>
        <div id="log"></div>
        <textarea id="message" placeholder="Ask about maps, routes, or POIs..."></textarea>
        <button onclick="sendMessage()">Send</button>
        <script>
            async function sendMessage() {
                const input = document.getElementById('message');
                const text = input.value.trim();
                if (!text) { return; }
                appendLog('You: ' + text);
                input.value = '';
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ message: text })
                });
                if (!response.ok) {
                    appendLog('Assistant: [Error ' + response.status + ']');
                    return;
                }
                const data = await response.json();
                appendLog('Assistant: ' + data.reply);
            }
            function appendLog(text) {
                const log = document.getElementById('log');
                log.textContent += text + '\\n\\n';
                log.scrollTop = log.scrollHeight;
            }
        </script>
    </body>
    </html>
    """


@app.post("/chat", response_class=JSONResponse)
async def chat(payload: dict) -> JSONResponse:
    message = (payload.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    agent: MapAssistant = app.state.agent
    reply = await agent.ask(message)
    return JSONResponse({"reply": reply})


if __name__ == "__main__":
    uvicorn.run("web_app:app", host="0.0.0.0", port=8000, reload=True)
