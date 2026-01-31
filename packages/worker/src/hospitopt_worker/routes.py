"""Google Routes API helpers for travel-time matrices."""

import math
from datetime import datetime, timedelta, timezone

from google.maps import routing_v2
from google.type import latlng_pb2

from hospitopt_core.domain.models import (
    Ambulance,
    AmbulanceIndex,
    Hospital,
    HospitalIndex,
    MinutesTables,
    Patient,
    PatientIndex,
    RouteMatrixEntry,
)


async def _compute_route_matrix_minutes(
    client: routing_v2.RoutesAsyncClient,
    origins: list[tuple[float, float]],
    destinations: list[tuple[float, float]],
    travel_mode: routing_v2.RouteTravelMode = routing_v2.RouteTravelMode.DRIVE,
    routing_preference: routing_v2.RoutingPreference = routing_v2.RoutingPreference.TRAFFIC_AWARE_OPTIMAL,
) -> list[RouteMatrixEntry]:
    """Compute a route matrix and return duration minutes by origin/destination index.

    Args:
        client: Google Routes async client.
        origins: List of (lat, lon) origin coordinates.
        destinations: List of (lat, lon) destination coordinates.
        travel_mode: Google Routes travel mode. Defaults to DRIVE.
        routing_preference: Google Routes routing preference. Defaults to TRAFFIC_AWARE_OPTIMAL.

    Returns:
        List of RouteMatrixEntry with duration minutes for each origin/destination pair.
    """
    entries: list[RouteMatrixEntry] = []

    # Google Routes limits to 100 elements when using TRAFFIC_AWARE_OPTIMAL.
    # Batch requests while preserving global indices.
    max_elements = 100
    if routing_preference == routing_v2.RoutingPreference.TRAFFIC_AWARE_OPTIMAL:
        max_elements = 100

    def _chunk_coords(coords: list[tuple[float, float]], size: int) -> list[tuple[int, list[tuple[float, float]]]]:
        return [(start, coords[start : start + size]) for start in range(0, len(coords), size)]

    if not origins or not destinations:
        return entries

    max_origins = max(1, min(len(origins), max_elements))
    max_destinations = max(1, max_elements // max_origins)

    for origin_offset, origin_chunk in _chunk_coords(origins, max_origins):
        for dest_offset, dest_chunk in _chunk_coords(destinations, max_destinations):
            request = routing_v2.ComputeRouteMatrixRequest(
                origins=[
                    routing_v2.RouteMatrixOrigin(
                        waypoint=routing_v2.Waypoint(
                            location=routing_v2.Location(lat_lng=latlng_pb2.LatLng(latitude=lat, longitude=lon))
                        )
                    )
                    for (lat, lon) in origin_chunk
                ],
                destinations=[
                    routing_v2.RouteMatrixDestination(
                        waypoint=routing_v2.Waypoint(
                            location=routing_v2.Location(lat_lng=latlng_pb2.LatLng(latitude=lat, longitude=lon))
                        )
                    )
                    for (lat, lon) in dest_chunk
                ],
                travel_mode=travel_mode,
                routing_preference=routing_v2.RoutingPreference(routing_preference),
                departure_time=datetime.now(timezone.utc)
                + timedelta(seconds=30),  # otherwise it complains that departure time is in the past.
            )
            stream = await client.compute_route_matrix(
                request=request,
                metadata=[("x-goog-fieldmask", "duration,distance_meters,origin_index,destination_index")],
            )
            async for element in stream:
                if element.status and element.status.code != 0:
                    # Skip invalid pairs
                    continue
                entries.append(
                    RouteMatrixEntry(
                        origin_index=origin_offset + element.origin_index,
                        destination_index=dest_offset + element.destination_index,
                        duration_minutes=max(1, int(math.ceil(element.duration.total_seconds() / 60))),
                    )
                )
    return entries


async def build_minutes_tables(
    client: routing_v2.RoutesAsyncClient,
    patients: list[Patient],
    hospitals: list[Hospital],
    ambulances: list[Ambulance],
    travel_mode: routing_v2.RouteTravelMode = routing_v2.RouteTravelMode.DRIVE,
) -> MinutesTables:
    """Build patient -> hospital and ambulance -> patient duration tables in minutes.

    Args:
        client: Google Routes async client.
        patients: List of patients.
        hospitals: List of hospitals.
        ambulances: List of ambulances.
        travel_mode: Google Routes travel mode. Defaults to DRIVE.

    Returns:
        MinutesTables with patient_to_hospital and ambulance_to_patient dicts.
    """
    patient_coords = [(p.lat, p.lon) for p in patients]
    hospital_coords = [(h.lat, h.lon) for h in hospitals]
    p_to_h = await _compute_route_matrix_minutes(
        client,
        origins=patient_coords,
        destinations=hospital_coords,
        travel_mode=travel_mode,
    )
    ambulance_coords = [(a.lat, a.lon) for a in ambulances]
    a_to_p = await _compute_route_matrix_minutes(
        client,
        origins=ambulance_coords,
        destinations=patient_coords,
        travel_mode=travel_mode,
    )
    return MinutesTables(
        ambulance_to_patient={
            (AmbulanceIndex(e.origin_index), PatientIndex(e.destination_index)): e.duration_minutes for e in a_to_p
        },
        patient_to_hospital={
            (PatientIndex(e.origin_index), HospitalIndex(e.destination_index)): e.duration_minutes for e in p_to_h
        },
    )
