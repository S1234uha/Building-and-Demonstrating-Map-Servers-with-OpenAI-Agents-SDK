## Assignment Deliverables

This repository contains an end-to-end response to the “Building and Demonstrating Map Servers with OpenAI Agents SDK” brief. The work is split into four artifacts:

1. [`SUMMARY.md`](SUMMARY.md) – 360-word write-up covering the MCP article and existing map server patterns.
2. `map_agents/` – Python package that implements two MCP-style servers (`OpenStreetMapServer`, `OSRMRoutingServer`) plus the glue code (`MapToolkit`, `MapAssistant`) required to plug them into the OpenAI Assistants (Agents) SDK.
3. [`app.py`](app.py) – Async CLI that spins up the toolkit and routes user prompts through the OpenAI assistant.
4. [`REFLECTION.md`](REFLECTION.md) – short retrospective on lessons learned and next steps.

### Requirements

- Python 3.11+
- Pip packages: `openai>=1.40.0`, `httpx>=0.27.0`, `pytest`, `pytest-asyncio`, `fastapi`, `uvicorn`, `python-dotenv`
- Environment variables: `OPENAI_API_KEY`, optional `OPENAI_MODEL` (defaults to `gpt-4o-mini`)

Install the dependencies inside a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install openai httpx pytest pytest-asyncio
```

Add the optional chatbot dependencies:

```powershell
python -m pip install fastapi uvicorn python-dotenv
```

### Running the demo assistant

1. Export your OpenAI API key: `setx OPENAI_API_KEY "sk-..."` (Windows) or `export OPENAI_API_KEY=...` (macOS/Linux).
2. Optionally set `OPENAI_MODEL` to select any tool-capable model (e.g., `gpt-4o-mini`).
3. Start the CLI: `python app.py`.
4. Type natural-language queries like _“Find three coffee shops near the Eiffel Tower and plot a walking route.”_  
   The assistant stream will create a run, call the map servers via MCP-style tools, and surface the stitched answer in your terminal.

#### Lebanon-focused sample prompts
- "Geocode Beirut Rafic Hariri International Airport and reverse geocode its coordinates."
- "Find five `amenity=cafe` POIs within [33.87, 35.48, 33.92, 35.54] (central Beirut)."
- "Request a driving route from Martyrs' Square to Jeita Grotto and summarize the distance (meters + kilometers)."
- "Build a distance matrix for Beirut, Tripoli, and Sidon (results now include meters and kilometers)."

### Browser-based chatbot

Prefer a web UI? Launch the FastAPI app:

```powershell
uvicorn web_app:app --reload
```

Open http://127.0.0.1:8000 to chat in the browser. The interface reuses the same `MapAssistant`, so the behavior matches the CLI while keeping conversation history visible.

### Tests and verification

Unit tests rely on `httpx.MockTransport` so they do not hit real map endpoints:

```powershell
pytest
```

### Screencast checklist

When recording the required 5–7 minute screencast:

1. Start with a 60-second architecture overview (show the README diagram and summarize the servers).
2. Launch `python app.py`, ask at least three questions (geocoding, POI search, routing) so every tool is exercised.
3. Narrate how tool calls appear in the OpenAI dashboard (or describe the logs shown in the terminal).
4. Close with lessons learned + mention of next steps (see `REFLECTION.md` for talking points).

Sharing suggestions: upload the video as an unlisted YouTube link or DropBox share and include that URL alongside this repo.
