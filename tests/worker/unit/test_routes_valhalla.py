import httpx
import pytest

from hospitopt_core.domain.models import Ambulance, Hospital, Patient
from hospitopt_worker import routes_valhalla


class _MockTransport(httpx.AsyncBaseTransport):
    """Return a canned Valhalla ``/sources_to_targets`` response."""

    def __init__(self, response_json: dict, status_code: int = 200) -> None:
        self._json = response_json
        self._status = status_code

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(self._status, json=self._json, request=request)


@pytest.mark.asyncio
async def test_compute_route_matrix_minutes_basic():
    """Basic 2-origin x 1-destination matrix."""
    response = {
        "sources_to_targets": [
            [{"from_index": 0, "to_index": 0, "time": 720}],  # 12 min
            [{"from_index": 1, "to_index": 0, "time": 90}],  # 1.5 min -> ceil = 2
        ]
    }
    async with httpx.AsyncClient(transport=_MockTransport(response), base_url="http://valhalla") as client:
        entries = await routes_valhalla._compute_route_matrix_minutes(
            client,
            origins=[(52.0, 4.0), (52.1, 4.1)],
            destinations=[(52.2, 4.2)],
        )

    assert len(entries) == 2
    assert entries[0].origin_index == 0
    assert entries[0].duration_minutes == 12
    assert entries[1].origin_index == 1
    assert entries[1].duration_minutes == 2


@pytest.mark.asyncio
async def test_compute_route_matrix_minutes_skips_null_time():
    """Unreachable pairs (time=None) are omitted."""
    response = {
        "sources_to_targets": [
            [{"from_index": 0, "to_index": 0, "time": None}],
        ]
    }
    async with httpx.AsyncClient(transport=_MockTransport(response), base_url="http://valhalla") as client:
        entries = await routes_valhalla._compute_route_matrix_minutes(
            client,
            origins=[(52.0, 4.0)],
            destinations=[(52.2, 4.2)],
        )

    assert entries == []


@pytest.mark.asyncio
async def test_compute_route_matrix_minutes_empty_inputs():
    async with httpx.AsyncClient(transport=_MockTransport({}), base_url="http://valhalla") as client:
        assert await routes_valhalla._compute_route_matrix_minutes(client, [], [(1.0, 1.0)]) == []
        assert await routes_valhalla._compute_route_matrix_minutes(client, [(1.0, 1.0)], []) == []


@pytest.mark.asyncio
async def test_build_minutes_tables():
    """Integration-style test: build_minutes_tables delegates to _compute correctly."""
    call_log: list[dict] = []

    async def fake_compute(client, origins, destinations, costing="auto"):
        call_log.append({"origins": origins, "destinations": destinations})
        return [
            routes_valhalla.RouteMatrixEntry(
                origin_index=0,
                destination_index=0,
                duration_minutes=len(origins) + len(destinations),
            )
        ]

    import hospitopt_worker.routes_valhalla as mod

    original = mod._compute_route_matrix_minutes
    mod._compute_route_matrix_minutes = fake_compute  # type: ignore[assignment]
    try:
        patients = [Patient(lat=0.0, lon=0.0, time_to_hospital_minutes=10)]
        hospitals = [Hospital(name="H", bed_capacity=1, used_beds=0, lat=1.0, lon=1.0)]
        ambulances = [Ambulance(lat=2.0, lon=2.0)]

        tables = await routes_valhalla.build_minutes_tables(
            client=httpx.AsyncClient(),
            patients=patients,
            hospitals=hospitals,
            ambulances=ambulances,
        )

        assert tables.patient_to_hospital == {(0, 0): 2}
        assert tables.ambulance_to_patient == {(0, 0): 2}
        assert len(call_log) == 2  # p->h and a->p
    finally:
        mod._compute_route_matrix_minutes = original  # type: ignore[assignment]
