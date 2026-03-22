"""Fake API with simulated ambulance movement following real roads.

Uses a self-hosted Valhalla instance to compute road-following routes,
then animates ambulances along the decoded polylines.  Exposes the same
``/hospitals``, ``/patients``, ``/ambulances`` endpoints that
``APIIngestor`` expects, so you can point the worker at it during
development.

Usage::

    uv run python scripts/fake_api.py [--valhalla-url http://localhost:8002]

The simulation uses a fixed set of 2 hospitals and a limited fleet of
ambulances that always spawn at the same positions.  Each ambulance
cycles:  spawn → pick up patient → deliver to hospital → next patient.

The background loop, every *tick* seconds:

1. Assigns idle ambulances to the nearest unassigned patient.
2. Fetches a road route (polyline) via Google Maps Routes API.
3. Moves ambulances one waypoint per tick (slow, realistic pace).
4. Once an ambulance reaches its patient it routes to the nearest
   hospital, delivers the patient, and becomes idle for the next one.
5. A new random patient spawns periodically to keep the scenario alive.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import math
import random
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from enum import Enum, auto
from uuid import UUID, uuid4

import httpx
from fastapi import FastAPI, Query
from pydantic import BaseModel

from hospitopt_core.domain.models import Ambulance, Hospital, Patient, PatientStatus

logger = logging.getLogger("fake_api")

# ---------------------------------------------------------------------------
# Polyline decoding (Google Encoded Polyline Algorithm)
# ---------------------------------------------------------------------------


def _decode_polyline(encoded: str, precision: int = 5) -> list[tuple[float, float]]:
    """Decode a Google-encoded polyline into a list of (lat, lon) tuples.

    Args:
        encoded: The encoded polyline string.
        precision: Coordinate precision (5 for Google, 6 for Valhalla).
    """
    factor = 10**precision
    coords: list[tuple[float, float]] = []
    index = 0
    lat = 0
    lng = 0
    while index < len(encoded):
        for is_lng in (False, True):
            shift = 0
            result = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if (result & 1) else (result >> 1)
            if is_lng:
                lng += delta
            else:
                lat += delta
        coords.append((lat / factor, lng / factor))
    return coords


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Valhalla route fetching
# ---------------------------------------------------------------------------


async def _fetch_road_route(
    client: httpx.AsyncClient,
    origin: tuple[float, float],
    destination: tuple[float, float],
    costing: str = "auto",
) -> list[tuple[float, float]]:
    """Return waypoints along the road from *origin* to *destination* via Valhalla.

    Falls back to a straight line if the API call fails.
    """
    body = {
        "locations": [
            {"lat": origin[0], "lon": origin[1]},
            {"lat": destination[0], "lon": destination[1]},
        ],
        "costing": costing,
    }
    try:
        resp = await client.post("/route", json=body)
        resp.raise_for_status()
        data = resp.json()
        encoded = data["trip"]["legs"][0]["shape"]
        return _decode_polyline(encoded, precision=6)
    except Exception:
        logger.warning("Valhalla route call failed, falling back to straight line", exc_info=True)
        return [origin, destination]


# ---------------------------------------------------------------------------
# Simulation state
# ---------------------------------------------------------------------------


class _Phase(Enum):
    IDLE = auto()
    TO_PATIENT = auto()
    TO_HOSPITAL = auto()
    TO_SPAWN = auto()


class _AmbulanceState:
    __slots__ = (
        "id",
        "lat",
        "lon",
        "phase",
        "assigned_patient_id",
        "waypoints",
        "wp_index",
        "target_hospital_id",
        "spawn_index",
    )

    def __init__(self, id: UUID, lat: float, lon: float, spawn_index: int) -> None:
        self.id = id
        self.lat = lat
        self.lon = lon
        self.spawn_index = spawn_index
        self.phase: _Phase = _Phase.IDLE
        self.assigned_patient_id: UUID | None = None
        self.waypoints: list[tuple[float, float]] = []
        self.wp_index: int = 0
        self.target_hospital_id: UUID | None = None


def _distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return math.hypot(lat2 - lat1, lon2 - lon1)


# How many waypoints to advance per tick.  Each polyline segment is roughly
# 10-50 m; higher values make the animation snappier.
_WAYPOINTS_PER_TICK = 3


# Fixed hospital locations (Lisbon area)
_FIXED_HOSPITALS: list[dict] = [
    {"name": "Hospital Santa Maria", "lat": 38.7490, "lon": -9.1580, "bed_capacity": 20, "used_beds": 3},
    {"name": "Hospital São José", "lat": 38.7180, "lon": -9.1390, "bed_capacity": 15, "used_beds": 2},
]

# Fixed ambulance spawn points (always the same positions)
_FIXED_AMBULANCE_SPAWNS: list[tuple[float, float]] = [
    (38.7370, -9.1500),  # Spawn A – between the two hospitals
    (38.7220, -9.1450),  # Spawn B – southern sector
    (38.7400, -9.1350),  # Spawn C – eastern sector
]

# Patient names for the simulation
_PATIENT_NAMES: list[str] = [
    "Maria Silva",
    "João Santos",
    "Pedro Oliveira",
    "Inês Ferreira",
    "Miguel Pereira",
    "Tiago Almeida",
    "Sofia Martins",
    "Rui Sousa",
    "Diogo Lopes",
    "Mariana Gonçalves",
    "Leonor Carvalho",
    "Hugo Mendes",
]


class Simulation:
    """Mutable world state that the background loop advances."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        num_patients: int = 5,
        num_ambulances: int = 3,
        center_lat: float = 38.7267,
        center_lon: float = -9.1403,
        radius: float = 0.025,
        seed: int = 42,
    ) -> None:
        self._rng = random.Random(seed)
        self._http = http_client
        self._center_lat = center_lat
        self._center_lon = center_lon
        self._radius = radius

        self.hospitals = self._init_hospitals()
        self.patients: dict[UUID, Patient] = {p.id: p for p in self._gen_patients(num_patients)}
        self.ambulances: list[_AmbulanceState] = self._init_ambulances(num_ambulances)
        self._assigned_patient_ids: set[UUID] = set()

    # -- public snapshot for the API -----------------------------------------

    def hospital_list(self) -> list[Hospital]:
        return list(self.hospitals)

    def patient_list(self) -> list[Patient]:
        return list(self.patients.values())

    def ambulance_list(self) -> list[Ambulance]:
        return [
            Ambulance(id=a.id, lat=a.lat, lon=a.lon, assigned_patient_id=a.assigned_patient_id) for a in self.ambulances
        ]

    # -- tick ----------------------------------------------------------------

    async def tick(self) -> None:
        for amb in self.ambulances:
            if amb.phase == _Phase.IDLE:
                await self._try_assign(amb)
            elif amb.phase == _Phase.TO_SPAWN:
                # Interrupt return-to-spawn if a patient needs pickup
                unassigned = [
                    p
                    for p in self.patients.values()
                    if p.id not in self._assigned_patient_ids and p.status == PatientStatus.WAITING
                ]
                if unassigned:
                    amb.waypoints = []
                    amb.wp_index = 0
                    amb.phase = _Phase.IDLE
                    await self._try_assign(amb)
                else:
                    self._advance(amb)
            elif amb.phase in (_Phase.TO_PATIENT, _Phase.TO_HOSPITAL):
                self._advance(amb)

    def _is_at_spawn(self, amb: _AmbulanceState) -> bool:
        sp = _FIXED_AMBULANCE_SPAWNS[amb.spawn_index]
        return _distance(amb.lat, amb.lon, sp[0], sp[1]) < 1e-6

    async def _try_assign(self, amb: _AmbulanceState) -> None:
        unassigned = [
            p
            for p in self.patients.values()
            if p.id not in self._assigned_patient_ids and p.status == PatientStatus.WAITING
        ]
        if not unassigned:
            if not self._is_at_spawn(amb):
                await self._route_to_spawn(amb)
            return
        nearest = min(unassigned, key=lambda p: _distance(amb.lat, amb.lon, p.lat, p.lon))
        amb.assigned_patient_id = nearest.id
        self._assigned_patient_ids.add(nearest.id)

        waypoints = await _fetch_road_route(
            self._http,
            (amb.lat, amb.lon),
            (nearest.lat, nearest.lon),
        )
        amb.waypoints = waypoints
        amb.wp_index = 0
        amb.phase = _Phase.TO_PATIENT
        logger.info("Ambulance %s assigned to patient %s (%d road waypoints)", amb.id, nearest.id, len(waypoints))

    def _advance(self, amb: _AmbulanceState) -> None:
        remaining = len(amb.waypoints) - amb.wp_index
        step = min(_WAYPOINTS_PER_TICK, remaining)
        if step > 0:
            amb.wp_index += step
            amb.lat, amb.lon = amb.waypoints[min(amb.wp_index, len(amb.waypoints) - 1)]

        # Keep the carried patient's location in sync with the ambulance
        if amb.phase == _Phase.TO_HOSPITAL and amb.assigned_patient_id:
            patient = self.patients.get(amb.assigned_patient_id)
            if patient:
                self.patients[amb.assigned_patient_id] = patient.model_copy(update={"lat": amb.lat, "lon": amb.lon})

        if amb.wp_index >= len(amb.waypoints) - 1:
            if amb.phase == _Phase.TO_PATIENT:
                self._on_reached_patient(amb)
            elif amb.phase == _Phase.TO_HOSPITAL:
                self._on_reached_hospital(amb)
            elif amb.phase == _Phase.TO_SPAWN:
                self._on_reached_spawn(amb)

    def _on_reached_patient(self, amb: _AmbulanceState) -> None:
        # Mark patient as picked up
        if amb.assigned_patient_id:
            patient = self.patients.get(amb.assigned_patient_id)
            if patient:
                self.patients[amb.assigned_patient_id] = patient.model_copy(
                    update={"status": PatientStatus.IN_TRANSIT, "lat": amb.lat, "lon": amb.lon}
                )
                logger.info("Patient %s picked up by ambulance %s", amb.assigned_patient_id, amb.id)
        nearest_hosp = min(self.hospitals, key=lambda h: _distance(amb.lat, amb.lon, h.lat, h.lon))
        amb.target_hospital_id = nearest_hosp.id
        # We'll fetch the route to the hospital async; park until next tick.
        amb.phase = _Phase.IDLE  # temporarily idle so the tick can re-route
        asyncio.get_event_loop().create_task(self._route_to_hospital(amb, nearest_hosp))

    async def _route_to_hospital(self, amb: _AmbulanceState, hosp: Hospital) -> None:
        waypoints = await _fetch_road_route(
            self._http,
            (amb.lat, amb.lon),
            (hosp.lat, hosp.lon),
        )
        amb.waypoints = waypoints
        amb.wp_index = 0
        amb.phase = _Phase.TO_HOSPITAL
        logger.info("Ambulance %s heading to hospital %s (%d road waypoints)", amb.id, hosp.name, len(waypoints))

    async def _route_to_spawn(self, amb: _AmbulanceState) -> None:
        """Send ambulance back to its spawn point when there are no patients."""
        sp = _FIXED_AMBULANCE_SPAWNS[amb.spawn_index]
        waypoints = await _fetch_road_route(
            self._http,
            (amb.lat, amb.lon),
            sp,
        )
        amb.waypoints = waypoints
        amb.wp_index = 0
        amb.phase = _Phase.TO_SPAWN
        logger.info("Ambulance %s returning to spawn %d", amb.id, amb.spawn_index)

    def _on_reached_spawn(self, amb: _AmbulanceState) -> None:
        sp = _FIXED_AMBULANCE_SPAWNS[amb.spawn_index]
        amb.lat, amb.lon = sp
        amb.waypoints = []
        amb.wp_index = 0
        amb.phase = _Phase.IDLE
        logger.info("Ambulance %s arrived at spawn %d", amb.id, amb.spawn_index)

    def _on_reached_hospital(self, amb: _AmbulanceState) -> None:
        pid = amb.assigned_patient_id
        if pid:
            # Mark patient as delivered before removing
            patient = self.patients.get(pid)
            if patient:
                self.patients[pid] = patient.model_copy(update={"status": PatientStatus.DELIVERED})
            self._assigned_patient_ids.discard(pid)
            logger.info("Patient %s delivered to hospital by ambulance %s", pid, amb.id)
        amb.assigned_patient_id = None
        amb.target_hospital_id = None
        amb.waypoints = []
        amb.wp_index = 0
        amb.phase = _Phase.IDLE  # will pick up next patient on the next tick
        self._maybe_spawn_patient()

    def _maybe_spawn_patient(self) -> None:
        """Spawn a new patient to keep the scenario alive."""
        name = self._rng.choice(_PATIENT_NAMES)
        p = Patient(
            id=uuid4(),
            name=name,
            lat=self._center_lat + self._rng.uniform(-self._radius, self._radius),
            lon=self._center_lon + self._rng.uniform(-self._radius, self._radius),
            time_to_hospital_minutes=self._rng.randint(15, 60),
            registered_at=datetime.now(UTC),
        )
        self.patients[p.id] = p
        logger.info("New patient %s (%s) spawned at (%.4f, %.4f)", p.id, name, p.lat, p.lon)

    # -- data generation -----------------------------------------------------

    def _init_hospitals(self) -> list[Hospital]:
        """Create the fixed set of 2 hospitals (positions never change)."""
        return [
            Hospital(
                id=uuid4(),
                name=h["name"],
                bed_capacity=h["bed_capacity"],
                used_beds=h["used_beds"],
                lat=h["lat"],
                lon=h["lon"],
            )
            for h in _FIXED_HOSPITALS
        ]

    def _gen_patients(self, n: int) -> list[Patient]:
        return [
            Patient(
                name=self._rng.choice(_PATIENT_NAMES),
                lat=self._center_lat + self._rng.uniform(-self._radius, self._radius),
                lon=self._center_lon + self._rng.uniform(-self._radius, self._radius),
                time_to_hospital_minutes=self._rng.randint(15, 60),
                registered_at=datetime.now(UTC),
            )
            for _ in range(n)
        ]

    def _init_ambulances(self, n: int) -> list[_AmbulanceState]:
        """Create *n* ambulances at fixed spawn points (cycling through available spawns)."""
        n = min(n, len(_FIXED_AMBULANCE_SPAWNS))  # cap to available spawn slots
        return [
            _AmbulanceState(
                id=uuid4(),
                lat=_FIXED_AMBULANCE_SPAWNS[i][0],
                lon=_FIXED_AMBULANCE_SPAWNS[i][1],
                spawn_index=i,
            )
            for i in range(n)
        ]


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

sim: Simulation | None = None
_tick_interval: float = 5.0


async def _simulation_loop() -> None:
    assert sim is not None
    while True:
        await sim.tick()
        await asyncio.sleep(_tick_interval)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    task = asyncio.create_task(_simulation_loop())
    logger.info("Simulation started (tick every %.1fs)", _tick_interval)
    yield
    task.cancel()


app = FastAPI(title="HospitOPT Fake API (Simulation)", version="0.2.0", lifespan=lifespan)


class HospitalsPage(BaseModel):
    items: list[Hospital]
    total: int
    limit: int
    offset: int


class PatientsPage(BaseModel):
    items: list[Patient]
    total: int
    limit: int
    offset: int


class AmbulancesPage(BaseModel):
    items: list[Ambulance]
    total: int
    limit: int
    offset: int


def _paginate[T](items: list[T], limit: int, offset: int) -> list[T]:
    return items[offset : offset + limit]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/hospitals", response_model=HospitalsPage)
async def get_hospitals(
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> HospitalsPage:
    assert sim is not None
    items = sim.hospital_list()
    page = _paginate(items, limit, offset)
    return HospitalsPage(items=page, total=len(items), limit=limit, offset=offset)


@app.get("/patients", response_model=PatientsPage)
async def get_patients(
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> PatientsPage:
    assert sim is not None
    items = sim.patient_list()
    page = _paginate(items, limit, offset)
    return PatientsPage(items=page, total=len(items), limit=limit, offset=offset)


@app.get("/ambulances", response_model=AmbulancesPage)
async def get_ambulances(
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> AmbulancesPage:
    assert sim is not None
    items = sim.ambulance_list()
    page = _paginate(items, limit, offset)
    return AmbulancesPage(items=page, total=len(items), limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Fake API with road-following simulation")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--tick", type=float, default=5.0, help="Seconds between simulation ticks")
    parser.add_argument("--patients", type=int, default=5)
    parser.add_argument("--ambulances", type=int, default=3, help="Max ambulances (capped to spawn slots)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--valhalla-url",
        default="http://localhost:8002",
        help="Valhalla server URL",
    )
    args = parser.parse_args()

    global sim, _tick_interval
    _tick_interval = args.tick
    sim = Simulation(
        http_client=httpx.AsyncClient(base_url=args.valhalla_url, timeout=10),
        num_patients=args.patients,
        num_ambulances=args.ambulances,
        seed=args.seed,
    )

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
