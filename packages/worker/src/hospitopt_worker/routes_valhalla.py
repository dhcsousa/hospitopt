"""Valhalla routing backend for travel-time matrices (free, self-hosted)."""

import math

import httpx

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
    client: httpx.AsyncClient,
    origins: list[tuple[float, float]],
    destinations: list[tuple[float, float]],
    costing: str = "auto",
) -> list[RouteMatrixEntry]:
    """Compute a travel-time matrix via the Valhalla ``/sources_to_targets`` endpoint.

    Args:
        client: httpx async client pointed at the Valhalla server.
        origins: List of (lat, lon) origin coordinates.
        destinations: List of (lat, lon) destination coordinates.
        costing: Valhalla costing model. Defaults to ``"auto"`` (car).

    Returns:
        List of RouteMatrixEntry with duration in minutes for each OD pair.
    """
    if not origins or not destinations:
        return []

    body = {
        "sources": [{"lat": lat, "lon": lon} for lat, lon in origins],
        "targets": [{"lat": lat, "lon": lon} for lat, lon in destinations],
        "costing": costing,
    }

    response = await client.post("/sources_to_targets", json=body)
    response.raise_for_status()
    data = response.json()

    entries: list[RouteMatrixEntry] = []
    for row in data["sources_to_targets"]:
        for cell in row:
            if cell.get("time") is None:
                continue  # unreachable pair
            entries.append(
                RouteMatrixEntry(
                    origin_index=cell["from_index"],
                    destination_index=cell["to_index"],
                    duration_minutes=max(1, int(math.ceil(cell["time"] / 60))),
                )
            )
    return entries


async def build_minutes_tables(
    client: httpx.AsyncClient,
    patients: list[Patient],
    hospitals: list[Hospital],
    ambulances: list[Ambulance],
    costing: str = "auto",
) -> MinutesTables:
    """Build patient -> hospital and ambulance -> patient duration tables.

    Args:
        client: httpx async client pointed at the Valhalla server.
        patients: List of patients.
        hospitals: List of hospitals.
        ambulances: List of ambulances.
        costing: Valhalla costing model. Defaults to ``"auto"`` (car).

    Returns:
        MinutesTables with patient_to_hospital and ambulance_to_patient dicts.
    """
    patient_coords = [(p.lat, p.lon) for p in patients]
    hospital_coords = [(h.lat, h.lon) for h in hospitals]
    ambulance_coords = [(a.lat, a.lon) for a in ambulances]

    p_to_h = await _compute_route_matrix_minutes(
        client,
        origins=patient_coords,
        destinations=hospital_coords,
        costing=costing,
    )
    a_to_p = await _compute_route_matrix_minutes(
        client,
        origins=ambulance_coords,
        destinations=patient_coords,
        costing=costing,
    )
    return MinutesTables(
        ambulance_to_patient={
            (AmbulanceIndex(e.origin_index), PatientIndex(e.destination_index)): e.duration_minutes for e in a_to_p
        },
        patient_to_hospital={
            (PatientIndex(e.origin_index), HospitalIndex(e.destination_index)): e.duration_minutes for e in p_to_h
        },
    )
