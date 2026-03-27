"""Fake API with simulated ambulance movement following real roads.

Uses a self-hosted Valhalla instance to compute road-following routes,
then animates ambulances along the decoded polylines.  Exposes the same
``/hospitals``, ``/patients``, ``/ambulances`` endpoints that
``APIIngestor`` expects, so you can point the worker at it during
development.

Usage::

    uv run python scripts/fake_api.py \
        --api-url http://localhost:8000 --api-key <key> \
        --valhalla-url http://localhost:8002

The simulation uses a fixed set of 2 hospitals and a limited fleet of
ambulances that always spawn at the same positions.  Each ambulance
follows the optimizer's assignments (polled from the real API):
pick up the assigned patient → deliver to the assigned hospital → idle.
A new random patient spawns after each delivery.

The simulator can also inject a clustered surge event after a configured
number of ticks to mimic a major incident in one area.

The background loop, every *tick* seconds:

1. Polls ``/assignments`` from the real API for optimizer decisions.
2. Dispatches idle ambulances according to their assignments.
3. Fetches road routes (polylines) via Valhalla.
4. Moves ambulances along waypoints.
5. Delivers patients to the assigned hospital, spawns new ones.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import math
import os
import random
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from enum import Enum, auto
from uuid import UUID, uuid4

import httpx
from fastapi import FastAPI, Query
from pydantic import BaseModel
from sqlalchemy import delete

from hospitopt_api.settings import APIConfig
from hospitopt_core.config.env import Environment
from hospitopt_core.db.models import AmbulanceDB, HospitalDB, PatientAssignmentDB, PatientDB
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


# Advance one waypoint per tick so higher speed can be expressed by shorter
# delays between ticks instead of skipping animation updates.
_WAYPOINTS_PER_TICK = 1


# Fixed hospital locations (Lisbon area)
_FIXED_HOSPITALS: list[dict] = [
    {"name": "Hospital Santa Maria", "lat": 38.7501, "lon": -9.1610, "bed_capacity": 80, "used_beds": 6},
    {"name": "Hospital São José", "lat": 38.7181, "lon": -9.1371, "bed_capacity": 60, "used_beds": 4},
]

# Fixed ambulance spawn points (always the same positions)
_FIXED_AMBULANCE_SPAWNS: list[tuple[float, float]] = [
    (38.7370, -9.1500),  # Spawn A – between the two hospitals
    (38.7220, -9.1450),  # Spawn B – southern sector
    (38.7400, -9.1350),  # Spawn C – eastern sector
]

_INCIDENT_LOCATION: tuple[float, float] = (38.7167, -9.1333)  # Downtown Lisbon / Baixa-Chiado

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
        valhalla_client: httpx.AsyncClient,
        api_client: httpx.AsyncClient,
        num_patients: int = 5,
        num_ambulances: int = 3,
        center_lat: float = 38.7267,
        center_lon: float = -9.1403,
        radius: float = 0.025,
        seed: int = 42,
        incident_tick: int = 12,
        incident_patients: int = 18,
        incident_radius: float = 0.003,
        incident_lat: float = _INCIDENT_LOCATION[0],
        incident_lon: float = _INCIDENT_LOCATION[1],
    ) -> None:
        self._rng = random.Random(seed)
        self._valhalla = valhalla_client
        self._api = api_client
        self._center_lat = center_lat
        self._center_lon = center_lon
        self._radius = radius
        self._wp_per_tick = _WAYPOINTS_PER_TICK
        self._tick_count = 0
        self._incident_tick = incident_tick
        self._incident_patients = incident_patients
        self._incident_radius = incident_radius
        self._incident_lat = incident_lat
        self._incident_lon = incident_lon
        self._incident_triggered = incident_patients <= 0 or incident_tick < 0

        self.hospitals = self._init_hospitals()
        self.patients: dict[UUID, Patient] = {p.id: p for p in self._gen_patients(num_patients)}
        self.ambulances: list[_AmbulanceState] = self._init_ambulances(num_ambulances)
        self._assigned_patient_ids: set[UUID] = set()
        # Optimizer assignments keyed by ambulance-id → (patient_id, hospital_id)
        self._optimizer_assignments: dict[UUID, tuple[UUID, UUID | None]] = {}

    # -- public snapshot for the API -----------------------------------------

    def hospital_list(self) -> list[Hospital]:
        return list(self.hospitals)

    def patient_list(self) -> list[Patient]:
        return list(self.patients.values())

    def ambulance_list(self) -> list[Ambulance]:
        return [
            Ambulance(id=a.id, lat=a.lat, lon=a.lon, assigned_patient_id=a.assigned_patient_id) for a in self.ambulances
        ]

    # -- optimizer integration -----------------------------------------------

    async def _poll_assignments(self) -> None:
        """Fetch the latest optimizer assignments from the real API."""
        try:
            resp = await self._api.get("/assignments", params={"limit": 500, "offset": 0})
            resp.raise_for_status()
            items = resp.json().get("items", [])
        except Exception:
            logger.debug("Could not fetch assignments from API", exc_info=True)
            return
        new_assignments: dict[UUID, tuple[UUID, UUID | None]] = {}
        for item in items:
            amb_id = item.get("ambulance_id")
            pat_id = item.get("patient_id")
            hosp_id = item.get("hospital_id")
            if not amb_id or not pat_id:
                continue
            try:
                amb_uuid = UUID(amb_id)
                pat_uuid = UUID(pat_id)
                hosp_uuid = UUID(hosp_id) if hosp_id else None
            except ValueError:
                continue

            # /assignments includes historical rows. Keep only the first viable
            # (newest) assignment per ambulance to avoid following stale plans.
            if amb_uuid in new_assignments:
                continue
            patient = self.patients.get(pat_uuid)
            if patient is None:
                continue
            if patient.status == PatientStatus.DELIVERED:
                continue
            if patient.status == PatientStatus.IN_TRANSIT and self._carrier_for_patient(pat_uuid) != amb_uuid:
                continue
            new_assignments[amb_uuid] = (pat_uuid, hosp_uuid)
        self._optimizer_assignments = new_assignments

    def _carrier_for_patient(self, patient_id: UUID) -> UUID | None:
        """Return the ambulance currently carrying *patient_id*, if any."""
        for amb in self.ambulances:
            if amb.assigned_patient_id == patient_id:
                return amb.id
        return None

    # -- tick ----------------------------------------------------------------

    async def tick(self) -> None:
        self._tick_count += 1
        self._maybe_trigger_incident()
        await self._poll_assignments()
        for amb in self.ambulances:
            if amb.phase == _Phase.IDLE:
                # An ambulance with a patient on board may be briefly IDLE while
                # the async hospital route is being fetched after pickup.
                # Do not treat it as available for reassignment during that gap.
                if amb.assigned_patient_id is None:
                    await self._try_assign(amb)
            elif amb.phase == _Phase.TO_SPAWN:
                # Interrupt return-to-spawn only if the assignment is for a WAITING patient
                if self._has_viable_assignment(amb):
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

    def _has_viable_assignment(self, amb: _AmbulanceState) -> bool:
        """Return True if the optimizer assignment points to a WAITING patient."""
        assignment = self._optimizer_assignments.get(amb.id)
        if assignment is None:
            return False
        patient = self.patients.get(assignment[0])
        return patient is not None and patient.status == PatientStatus.WAITING

    async def _try_assign(self, amb: _AmbulanceState) -> None:
        assignment = self._optimizer_assignments.get(amb.id)
        if assignment is None:
            # No optimizer assignment for this ambulance — return to spawn
            if not self._is_at_spawn(amb):
                await self._route_to_spawn(amb)
            return
        patient_id, hospital_id = assignment
        patient = self.patients.get(patient_id)
        if patient is None or patient.status != PatientStatus.WAITING:
            # Stale assignment — clear it so it doesn't keep interrupting
            del self._optimizer_assignments[amb.id]
            if not self._is_at_spawn(amb):
                await self._route_to_spawn(amb)
            return

        amb.assigned_patient_id = patient_id
        amb.target_hospital_id = hospital_id
        self._assigned_patient_ids.add(patient_id)

        waypoints = await _fetch_road_route(
            self._valhalla,
            (amb.lat, amb.lon),
            (patient.lat, patient.lon),
        )
        amb.waypoints = waypoints
        amb.wp_index = 0
        amb.phase = _Phase.TO_PATIENT
        logger.info(
            "Ambulance %s assigned to patient %s (optimizer) (%d road waypoints)", amb.id, patient_id, len(waypoints)
        )

    def _advance(self, amb: _AmbulanceState) -> None:
        remaining = len(amb.waypoints) - amb.wp_index
        step = min(self._wp_per_tick, remaining)
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
        # Use the hospital from the optimizer assignment (set in _try_assign)
        hosp = None
        if amb.target_hospital_id:
            for h in self.hospitals:
                if h.id == amb.target_hospital_id:
                    hosp = h
                    break
        if hosp is None:
            # Fallback: nearest hospital if optimizer didn't specify one
            hosp = min(self.hospitals, key=lambda h: _distance(amb.lat, amb.lon, h.lat, h.lon))
            amb.target_hospital_id = hosp.id
        # We'll fetch the route to the hospital async; park until next tick.
        amb.phase = _Phase.IDLE  # temporarily idle so the tick can re-route
        asyncio.get_event_loop().create_task(self._route_to_hospital(amb, hosp))

    async def _route_to_hospital(self, amb: _AmbulanceState, hosp: Hospital) -> None:
        waypoints = await _fetch_road_route(
            self._valhalla,
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
            self._valhalla,
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
            # Increment used_beds on the target hospital
            if amb.target_hospital_id:
                for i, h in enumerate(self.hospitals):
                    if h.id == amb.target_hospital_id:
                        self.hospitals[i] = h.model_copy(update={"used_beds": h.used_beds + 1})
                        break
            logger.info("Patient %s delivered to hospital by ambulance %s", pid, amb.id)
        amb.assigned_patient_id = None
        amb.target_hospital_id = None
        amb.waypoints = []
        amb.wp_index = 0
        amb.phase = _Phase.IDLE  # will pick up next patient on the next tick
        self._maybe_spawn_patient()

    def _maybe_spawn_patient(self) -> None:
        """Spawn a new patient to keep the scenario alive."""
        p = self._new_patient(
            center_lat=self._center_lat,
            center_lon=self._center_lon,
            radius=self._radius,
        )
        self.patients[p.id] = p
        logger.info("New patient %s (%s) spawned at (%.4f, %.4f)", p.id, p.name, p.lat, p.lon)

    def _maybe_trigger_incident(self) -> None:
        """Inject a one-time clustered incident after the configured delay."""
        if self._incident_triggered or self._tick_count < self._incident_tick:
            return
        self._incident_triggered = True
        new_patients = [
            self._new_patient(
                center_lat=self._incident_lat,
                center_lon=self._incident_lon,
                radius=self._incident_radius,
                min_deadline=8,
                max_deadline=25,
            )
            for _ in range(self._incident_patients)
        ]
        for patient in new_patients:
            self.patients[patient.id] = patient
        logger.warning(
            "Mass-casualty incident triggered at tick %d near (%.4f, %.4f): %d patients added",
            self._tick_count,
            self._incident_lat,
            self._incident_lon,
            len(new_patients),
        )

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
            self._new_patient(
                center_lat=self._center_lat,
                center_lon=self._center_lon,
                radius=self._radius,
            )
            for _ in range(n)
        ]

    def _new_patient(
        self,
        *,
        center_lat: float,
        center_lon: float,
        radius: float,
        min_deadline: int = 15,
        max_deadline: int = 60,
    ) -> Patient:
        return Patient(
            id=uuid4(),
            name=self._rng.choice(_PATIENT_NAMES),
            lat=center_lat + self._rng.uniform(-radius, radius),
            lon=center_lon + self._rng.uniform(-radius, radius),
            time_to_hospital_minutes=self._rng.randint(min_deadline, max_deadline),
            registered_at=datetime.now(UTC),
        )

    def _init_ambulances(self, n: int) -> list[_AmbulanceState]:
        """Create *n* ambulances distributed across the fixed spawn points."""
        ambulances: list[_AmbulanceState] = []
        for i in range(n):
            spawn_index = i % len(_FIXED_AMBULANCE_SPAWNS)
            spawn_lat, spawn_lon = _FIXED_AMBULANCE_SPAWNS[spawn_index]
            slot = i // len(_FIXED_AMBULANCE_SPAWNS)
            lane = (slot % 5) - 2
            rank = slot // 5
            lat_offset = rank * 0.00022
            lon_offset = lane * 0.00018
            ambulances.append(
                _AmbulanceState(
                    id=uuid4(),
                    lat=spawn_lat + lat_offset,
                    lon=spawn_lon + lon_offset,
                    spawn_index=spawn_index,
                )
            )
        return ambulances


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

sim: Simulation | None = None
_tick_interval: float = 5.0
_reset_db_on_start: bool = True


async def _clear_database() -> None:
    """Clear persisted simulation state before starting the fake API."""
    env = Environment()
    if not env.API_CONFIG_FILE_PATH:
        logger.warning("API_CONFIG_FILE_PATH not set; skipping startup DB reset")
        return

    config = APIConfig.from_yaml(env.API_CONFIG_FILE_PATH)
    engine, session_factory = config.db_connection.to_engine_session_factory()
    try:
        async with session_factory() as session:
            await session.execute(delete(PatientAssignmentDB))
            await session.execute(delete(AmbulanceDB))
            await session.execute(delete(PatientDB))
            await session.execute(delete(HospitalDB))
            await session.commit()
        logger.info("Cleared persisted hospitals, patients, ambulances, and assignments before simulator startup")
    finally:
        await engine.dispose()


async def _simulation_loop() -> None:
    assert sim is not None
    while True:
        await sim.tick()
        await asyncio.sleep(_tick_interval)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    if _reset_db_on_start:
        await _clear_database()
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
    parser.add_argument("--tick", type=float, default=0.2, help="Seconds between simulation ticks")
    parser.add_argument("--patients", type=int, default=5)
    parser.add_argument(
        "--ambulances",
        type=int,
        default=len(_FIXED_AMBULANCE_SPAWNS) * 10,
        help="Total ambulances in the simulation (default: 10 at each spawn)",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Time acceleration factor applied by reducing the delay between ticks (e.g. 5 = 5× more frequent updates)",
    )
    parser.add_argument("--incident-tick", type=int, default=12, help="Tick when the clustered incident starts")
    parser.add_argument(
        "--incident-patients",
        type=int,
        default=18,
        help="How many patients spawn in the clustered incident",
    )
    parser.add_argument(
        "--incident-radius",
        type=float,
        default=0.003,
        help="Radius of the clustered incident in degrees",
    )
    parser.add_argument("--incident-lat", type=float, default=_INCIDENT_LOCATION[0], help="Incident center latitude")
    parser.add_argument("--incident-lon", type=float, default=_INCIDENT_LOCATION[1], help="Incident center longitude")
    parser.add_argument(
        "--no-reset-db-on-start",
        action="store_true",
        help="Do not clear the API database tables when the simulator starts",
    )
    parser.add_argument(
        "--valhalla-url",
        default="http://localhost:8002",
        help="Valhalla server URL",
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="HospitOPT API URL (for polling optimizer assignments)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key for the HospitOPT API (defaults to HOSPITOPT_API_KEY env var)",
    )
    args = parser.parse_args()

    api_key = args.api_key or os.getenv("HOSPITOPT_API_KEY", "")
    api_headers: dict[str, str] = {}
    if api_key:
        api_headers["Authorization"] = f"Bearer {api_key}"

    global sim, _tick_interval, _reset_db_on_start
    _tick_interval = args.tick / max(args.speed, 0.01)
    _reset_db_on_start = not args.no_reset_db_on_start
    sim = Simulation(
        valhalla_client=httpx.AsyncClient(base_url=args.valhalla_url, timeout=10),
        api_client=httpx.AsyncClient(base_url=args.api_url, headers=api_headers, timeout=5),
        num_patients=args.patients,
        num_ambulances=args.ambulances,
        seed=args.seed,
        incident_tick=args.incident_tick,
        incident_patients=args.incident_patients,
        incident_radius=args.incident_radius,
        incident_lat=args.incident_lat,
        incident_lon=args.incident_lon,
    )

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
