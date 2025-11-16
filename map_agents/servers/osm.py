from __future__ import annotations

import textwrap
from typing import Any, Dict, List, Sequence

import httpx

from ..config import MapCommand, ServerMetadata
from .base import MapServer


class OpenStreetMapServer(MapServer):
    """Map server that wraps Nominatim and Overpass community endpoints."""

    NOMINATIM_URL = "https://nominatim.openstreetmap.org"
    OVERPASS_URL = "https://overpass-api.de/api/interpreter"

    def __init__(
        self,
        *,
        user_agent: str = "map-agents/0.1 (+https://example.com)",
        timeout: float = 15.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._headers = {
            "User-Agent": user_agent,
            "Accept-Language": "en",
        }
        self._timeout = timeout
        self._transport = transport
        metadata = ServerMetadata(
            server_id="openstreetmap",
            summary="Community maintained OpenStreetMap geocoding, reverse geocoding, and POI search.",
            provider="OpenStreetMap",
            docs_url="https://operations.osmfoundation.org/policies/nominatim/",
            attribution="© OpenStreetMap contributors",
            tags=["geocode", "poi", "open-data"],
        )
        commands = [
            MapCommand(
                name="osm_geocode",
                description="Forward geocode a place or address using Nominatim.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Full text query (city, address, landmark, etc.)."},
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                            "default": 3,
                            "description": "Maximum number of matches to return.",
                        },
                        "country_codes": {
                            "type": "string",
                            "description": "Comma separated ISO 2 country codes to restrict the search.",
                        },
                        "accept_language": {
                            "type": "string",
                            "description": "BCP 47 locale hint for localized names (e.g., 'en', 'fr').",
                        },
                    },
                    "required": ["query"],
                },
                handler=self.geocode,
                server=metadata.server_id,
            ),
            MapCommand(
                name="osm_reverse_geocode",
                description="Reverse geocode coordinates back to the closest named feature.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "latitude": {"type": "number"},
                        "longitude": {"type": "number"},
                        "zoom": {
                            "type": "integer",
                            "minimum": 3,
                            "maximum": 18,
                            "default": 16,
                            "description": "Level of detail requested (street vs. house).",
                        },
                    },
                    "required": ["latitude", "longitude"],
                },
                handler=self.reverse_geocode,
                server=metadata.server_id,
            ),
            MapCommand(
                name="osm_poi_search",
                description="Search for named points of interest using Overpass.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Optional case insensitive POI name substring. Leave blank to match any name.",
                            "default": "",
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 50,
                            "default": 15,
                            "description": "Maximum number of elements to return.",
                        },
                        "bbox": {
                            "type": "array",
                            "items": {"type": "number"},
                            "minItems": 4,
                            "maxItems": 4,
                            "description": "Optional bounding box [south, west, north, east] in WGS84.",
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional exact key=value tag filters (e.g., amenity=cafe).",
                        },
                    },
                },
                handler=self.poi_search,
                server=metadata.server_id,
            ),
        ]
        super().__init__(metadata=metadata, commands=commands)

    async def geocode(
        self,
        query: str,
        limit: int = 3,
        country_codes: str | None = None,
        accept_language: str | None = None,
    ) -> Dict[str, Any]:
        params = {
            "q": query,
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": limit,
        }
        if country_codes:
            params["countrycodes"] = country_codes
        headers = dict(self._headers)
        if accept_language:
            headers["Accept-Language"] = accept_language
        async with httpx.AsyncClient(
            base_url=self.NOMINATIM_URL,
            headers=headers,
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            response = await client.get("/search", params=params)
            response.raise_for_status()
        payload = response.json()
        results = [
            {
                "name": item.get("display_name"),
                "latitude": float(item["lat"]),
                "longitude": float(item["lon"]),
                "importance": item.get("importance"),
                "boundingbox": item.get("boundingbox"),
                "type": item.get("type"),
            }
            for item in payload
        ]
        return {"matches": results, "source": "nominatim"}

    async def reverse_geocode(self, latitude: float, longitude: float, zoom: int = 16) -> Dict[str, Any]:
        params = {
            "lat": latitude,
            "lon": longitude,
            "zoom": zoom,
            "format": "jsonv2",
            "addressdetails": 1,
        }
        async with httpx.AsyncClient(
            base_url=self.NOMINATIM_URL,
            headers=self._headers,
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            response = await client.get("/reverse", params=params)
            response.raise_for_status()
        payload = response.json()
        return {
            "display_name": payload.get("display_name"),
            "address": payload.get("address"),
            "osm_id": payload.get("osm_id"),
            "osm_type": payload.get("osm_type"),
        }

    async def poi_search(
        self,
        query: str | None = None,
        limit: int = 15,
        bbox: Sequence[float] | None = None,
        tags: Sequence[str] | None = None,
    ) -> Dict[str, Any]:
        bbox_clause = ""
        if bbox:
            if len(bbox) != 4:
                raise ValueError("bbox must contain [south, west, north, east]")
            south, west, north, east = bbox
            bbox_clause = f"({south},{west},{north},{east})"
        tag_filters = ""
        keyword_tags = {
            "restaurant": "amenity=restaurant",
            "restaurants": "amenity=restaurant",
            "cafe": "amenity=cafe",
            "cafes": "amenity=cafe",
            "coffee shop": "amenity=cafe",
            "coffee": "amenity=cafe",
        }
        normalized = (query or "").lower()
        actual_tags: List[str] = list(tags) if tags else []
        if not actual_tags:
            auto: List[str] = []
            for keyword, tag in keyword_tags.items():
                if keyword in normalized:
                    auto.append(tag)
            if auto:
                actual_tags = auto
        if actual_tags:
            for tag in actual_tags:
                if "=" in tag:
                    key, value = tag.split("=", 1)
                    tag_filters += f'["{key}"="{value}"]'
                else:
                    tag_filters += f'["{tag}"]'
        pattern = (query or "").strip()
        if pattern and len(pattern.split()) > 6:
            pattern = ""
        if pattern:
            escaped = pattern.replace('"', r"\"")
            base_selector = f'["name"~"{escaped}",i]{tag_filters}'
        else:
            base_selector = f'["name"]{tag_filters}'
        statement = textwrap.dedent(
            f"""
            [out:json][timeout:25];
            (
              node{bbox_clause}{base_selector};
              way{bbox_clause}{base_selector};
              relation{bbox_clause}{base_selector};
            );
            out center {limit};
            """
        ).strip()
        async with httpx.AsyncClient(
            timeout=self._timeout,
            transport=self._transport,
            headers={"User-Agent": self._headers["User-Agent"]},
        ) as client:
            response = await client.post(self.OVERPASS_URL, content=statement.encode("utf-8"))
            response.raise_for_status()
        payload = response.json()
        elements: List[Dict[str, Any]] = payload.get("elements", [])
        matches = []
        for element in elements[:limit]:
            center = element.get("center", {})
            lat = element.get("lat") or center.get("lat")
            lon = element.get("lon") or center.get("lon")
            matches.append(
                {
                    "id": element.get("id"),
                    "type": element.get("type"),
                    "name": (element.get("tags") or {}).get("name"),
                    "latitude": lat,
                    "longitude": lon,
                    "tags": element.get("tags"),
                }
            )
        return {"matches": matches, "query": pattern or "*", "limit": limit}
