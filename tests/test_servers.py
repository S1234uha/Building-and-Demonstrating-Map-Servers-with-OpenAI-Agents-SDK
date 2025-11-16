import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import httpx
import pytest

from map_agents.servers.osm import OpenStreetMapServer
from map_agents.servers.osrm import OSRMRoutingServer


@pytest.mark.asyncio
async def test_geocode_parses_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "search" in request.url.path:
            payload = [
                {"display_name": "Paris, France", "lat": "48.8566", "lon": "2.3522", "importance": 0.8}
            ]
            return httpx.Response(200, json=payload)
        raise AssertionError(f"Unexpected URL {request.url}")

    server = OpenStreetMapServer(transport=httpx.MockTransport(handler))
    result = await server.geocode("Paris", limit=1)
    assert result["matches"][0]["name"] == "Paris, France"
    assert pytest.approx(result["matches"][0]["latitude"], rel=1e-4) == 48.8566


@pytest.mark.asyncio
async def test_route_parses_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "/route/v1" in request.url.path:
            payload = {
                "routes": [
                    {
                        "distance": 1000,
                        "duration": 120,
                        "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
                        "legs": [
                            {"summary": "leg", "distance": 1000, "duration": 120, "steps": []},
                        ],
                    }
                ]
            }
            return httpx.Response(200, json=payload)
        raise AssertionError(f"Unexpected URL {request.url}")

    server = OSRMRoutingServer(transport=httpx.MockTransport(handler))
    result = await server.route(0, 0, 1, 1)
    assert result["distance_m"] == 1000
    assert result["distance_km"] == 1.0
    assert result["duration_s"] == 120
    assert result["duration_min"] == 2
    assert len(result["legs"]) == 1


@pytest.mark.asyncio
async def test_matrix_requires_coordinates() -> None:
    server = OSRMRoutingServer()
    with pytest.raises(ValueError):
        await server.matrix([])


@pytest.mark.asyncio
async def test_matrix_returns_km_and_m() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "/table/v1" in request.url.path:
            payload = {
                "distances": [[0, 2000], [2000, 0]],
                "durations": [[0, 120], [120, 0]],
                "sources": [],
                "destinations": [],
            }
            return httpx.Response(200, json=payload)
        raise AssertionError("unexpected url")

    server = OSRMRoutingServer(transport=httpx.MockTransport(handler))
    result = await server.matrix(
        [
            {"lat": 0, "lon": 0},
            {"lat": 1, "lon": 1},
        ]
    )
    assert result["distances_m"][0][1] == 2000
    assert result["distances_km"][0][1] == 2
    assert result["durations_s"][0][1] == 120
    assert result["durations_min"][0][1] == 2


@pytest.mark.asyncio
async def test_poi_search_allows_empty_query() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "overpass" in request.url.host
        payload = {"elements": [{"id": 1, "type": "node", "tags": {"name": "Cafe A"}, "lat": 48.0, "lon": 2.0}]}
        return httpx.Response(200, json=payload)

    server = OpenStreetMapServer(transport=httpx.MockTransport(handler))
    result = await server.poi_search(query="", tags=["amenity=cafe"], limit=1)
    assert result["matches"][0]["name"] == "Cafe A"


@pytest.mark.asyncio
async def test_poi_search_autodetects_restaurant_tag_for_sentence() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        assert '["amenity"="restaurant"]' in body
        payload = {"elements": [{"id": 2, "type": "node", "tags": {"name": "Restaurant B"}, "lat": 33.89, "lon": 35.48}]}
        return httpx.Response(200, json=payload)

    server = OpenStreetMapServer(transport=httpx.MockTransport(handler))
    sentence = "Find five restaurant near American university of Beirut main gate"
    result = await server.poi_search(query=sentence, limit=1)
    assert result["matches"][0]["name"] == "Restaurant B"
