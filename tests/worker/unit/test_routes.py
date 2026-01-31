from datetime import timedelta

import pytest

from hospitopt_core.domain.models import Ambulance, Hospital, Patient
from hospitopt_worker import routes


class _Status:
    def __init__(self, code: int) -> None:
        self.code = code


class _Element:
    def __init__(self, origin_index: int, destination_index: int, duration: timedelta, status_code: int = 0) -> None:
        self.origin_index = origin_index
        self.destination_index = destination_index
        self.duration = duration
        self.status = _Status(status_code)


async def _async_gen(elements):
    for element in elements:
        yield element


class _DummyClient:
    def __init__(self, elements):
        self.elements = elements
        self.last_metadata = None

    async def compute_route_matrix(self, request, metadata=None):
        self.last_metadata = metadata
        return _async_gen(self.elements)


@pytest.mark.asyncio
async def test_compute_route_matrix_minutes_filters_invalid():
    elements = [
        _Element(0, 0, duration=timedelta(minutes=12), status_code=0),
        _Element(0, 1, duration=timedelta(minutes=20), status_code=3),
        _Element(1, 0, duration=timedelta(minutes=15), status_code=0),
    ]
    client = _DummyClient(elements)

    result = await routes._compute_route_matrix_minutes(
        client,
        origins=[(0.0, 0.0), (1.0, 1.0)],
        destinations=[(2.0, 2.0), (3.0, 3.0)],
    )

    assert result == [
        routes.RouteMatrixEntry(origin_index=0, destination_index=0, duration_minutes=12),
        routes.RouteMatrixEntry(origin_index=1, destination_index=0, duration_minutes=15),
    ]
    assert client.last_metadata == [("x-goog-fieldmask", "duration,distance_meters,origin_index,destination_index")]


@pytest.mark.asyncio
async def test_build_minutes_tables_uses_compute(monkeypatch):
    async def fake_compute(client, origins, destinations, travel_mode=None):
        return [
            routes.RouteMatrixEntry(
                origin_index=0,
                destination_index=0,
                duration_minutes=len(origins) + len(destinations),
            )
        ]

    monkeypatch.setattr(routes, "_compute_route_matrix_minutes", fake_compute)

    patients = [Patient(lat=0.0, lon=0.0, time_to_hospital_minutes=10)]
    hospitals = [Hospital(name="H", bed_capacity=1, used_beds=0, lat=1.0, lon=1.0)]
    ambulances = [Ambulance(lat=2.0, lon=2.0)]

    minutes_tables = await routes.build_minutes_tables(
        client=None,
        patients=patients,
        hospitals=hospitals,
        ambulances=ambulances,
    )

    assert minutes_tables.patient_to_hospital == {(0, 0): 2}
    assert minutes_tables.ambulance_to_patient == {(0, 0): 2}
