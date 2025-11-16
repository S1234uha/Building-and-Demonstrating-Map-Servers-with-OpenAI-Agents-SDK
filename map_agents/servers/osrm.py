from __future__ import annotations

from typing import Any, Dict, Iterable, Sequence

import httpx

from ..config import MapCommand, ServerMetadata
from .base import MapServer


class OSRMRoutingServer(MapServer):
    """Map server that wraps the public OSRM routing endpoints."""

    BASE_URL = "https://router.project-osrm.org"

    def __init__(
        self,
        *,
        timeout: float = 15.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._timeout = timeout
        self._transport = transport
        metadata = ServerMetadata(
            server_id="osrm",
            summary="Project OSRM routing, table, and nearest endpoints.",
            provider="Project OSRM",
            docs_url="http://project-osrm.org/docs/v5.5.1/api/",
            attribution="© OpenStreetMap contributors, Project OSRM",
            tags=["routing", "distance-matrix"],
        )
        commands = [
            MapCommand(
                name="osrm_route",
                description="Compute a route between an origin and a destination.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "start_lat": {"type": "number"},
                        "start_lon": {"type": "number"},
                        "end_lat": {"type": "number"},
                        "end_lon": {"type": "number"},
                        "profile": {
                            "type": "string",
                            "enum": ["driving", "walking", "cycling"],
                            "default": "driving",
                        },
                        "overview": {
                            "type": "string",
                            "enum": ["simplified", "full", "false"],
                            "default": "simplified",
                            "description": "Geometry detail level.",
                        },
                    },
                    "required": ["start_lat", "start_lon", "end_lat", "end_lon"],
                },
                handler=self.route,
                server=metadata.server_id,
            ),
            MapCommand(
                name="osrm_matrix",
                description="Return a travel time and distance matrix for multiple coordinates.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "coordinates": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "lat": {"type": "number"},
                                    "lon": {"type": "number"},
                                },
                                "required": ["lat", "lon"],
                            },
                            "minItems": 2,
                            "maxItems": 12,
                        },
                        "profile": {
                            "type": "string",
                            "enum": ["driving", "walking", "cycling"],
                            "default": "driving",
                        },
                    },
                    "required": ["coordinates"],
                },
                handler=self.matrix,
                server=metadata.server_id,
            ),
            MapCommand(
                name="osrm_nearest",
                description="Snap a coordinate to the nearest routable road.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "latitude": {"type": "number"},
                        "longitude": {"type": "number"},
                        "profile": {
                            "type": "string",
                            "enum": ["driving", "walking", "cycling"],
                            "default": "driving",
                        },
                    },
                    "required": ["latitude", "longitude"],
                },
                handler=self.nearest,
                server=metadata.server_id,
            ),
        ]
        super().__init__(metadata=metadata, commands=commands)

    async def route(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
        profile: str = "driving",
        overview: str = "simplified",
    ) -> Dict[str, Any]:
        coords = f"{start_lon},{start_lat};{end_lon},{end_lat}"
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.get(
                f"{self.BASE_URL}/route/v1/{profile}/{coords}",
                params={"overview": overview, "geometries": "geojson"},
            )
            response.raise_for_status()
        payload = response.json()
        routes = payload.get("routes", [])
        if not routes:
            return {"routes": []}
        best = routes[0]
        distance_m = best.get("distance")
        duration_s = best.get("duration")
        legs = [
            {
                "summary": leg.get("summary"),
                "distance_m": leg.get("distance"),
                "distance_km": (leg.get("distance") or 0) / 1000 if leg.get("distance") is not None else None,
                "duration_s": leg.get("duration"),
                "duration_min": (leg.get("duration") or 0) / 60 if leg.get("duration") is not None else None,
                "steps": leg.get("steps"),
            }
            for leg in best.get("legs", [])
        ]
        return {
            "distance_m": distance_m,
            "distance_km": distance_m / 1000 if distance_m is not None else None,
            "duration_s": duration_s,
            "duration_min": duration_s / 60 if duration_s is not None else None,
            "geometry": best.get("geometry"),
            "legs": legs,
        }

    async def matrix(
        self,
        coordinates: Sequence[Dict[str, float]],
        profile: str = "driving",
    ) -> Dict[str, Any]:
        if len(coordinates) < 2:
            raise ValueError("matrix requires at least two coordinates")
        for index, item in enumerate(coordinates):
            if "lat" not in item or "lon" not in item:
                raise ValueError(f"coordinate at index {index} is missing lat/lon keys")
        ordered = ";".join(f"{item['lon']},{item['lat']}" for item in coordinates)
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.get(
                f"{self.BASE_URL}/table/v1/{profile}/{ordered}",
                params={"annotations": "duration,distance"},
            )
            response.raise_for_status()
        payload = response.json()
        distances = payload.get("distances")
        distances_km = None
        if distances:
            distances_km = [
                [(value / 1000 if value is not None else None) for value in row]
                for row in distances
            ]
        durations = payload.get("durations")
        durations_min = None
        if durations:
            durations_min = [
                [(value / 60 if value is not None else None) for value in row]
                for row in durations
            ]
        return {
            "distances_m": distances,
            "distances_km": distances_km,
            "durations_s": durations,
            "durations_min": durations_min,
            "sources": payload.get("sources"),
            "destinations": payload.get("destinations"),
        }

    async def nearest(self, latitude: float, longitude: float, profile: str = "driving") -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.get(
                f"{self.BASE_URL}/nearest/v1/{profile}/{longitude},{latitude}",
            )
            response.raise_for_status()
        payload = response.json()
        waypoints = payload.get("waypoints") or []
        if not waypoints:
            return {"waypoint": None}
        point = waypoints[0]
        distance_m = point.get("distance")
        return {
            "name": point.get("name"),
            "latitude": point.get("location", [None, None])[1],
            "longitude": point.get("location", [None, None])[0],
            "distance_m": distance_m,
            "distance_km": distance_m / 1000 if distance_m is not None else None,
        }
