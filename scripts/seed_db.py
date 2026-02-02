"""Seed the database with demo data for hospitals, patients, and ambulances."""

import argparse
import asyncio
import random
from datetime import UTC, datetime, timedelta
from typing import Iterable

from pydantic import BaseModel

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from hospitopt_core.config.env import Environment
from hospitopt_core.db.models import AmbulanceDB, HospitalDB, PatientDB
from hospitopt_worker.settings import WorkerConfig


class SeedConfig(BaseModel):
    hospitals: int
    patients: int
    ambulances: int
    center_lat: float
    center_lon: float
    spread_km: float
    wipe: bool


def _random_offset_degrees(spread_km: float) -> tuple[float, float]:
    # Approx conversion: 1 degree lat ~ 111 km, lon scaled by cos(lat) later
    delta_lat = random.uniform(-spread_km, spread_km) / 111.0
    delta_lon = random.uniform(-spread_km, spread_km) / 111.0
    return delta_lat, delta_lon


def _iter_hospitals(config: SeedConfig) -> Iterable[HospitalDB]:
    for index in range(1, config.hospitals + 1):
        dlat, dlon = _random_offset_degrees(config.spread_km)
        bed_capacity = random.randint(40, 150)
        used_beds = random.randint(0, bed_capacity)
        yield HospitalDB(
            name=f"Hospital {index}",
            bed_capacity=bed_capacity,
            used_beds=used_beds,
            lat=config.center_lat + dlat,
            lon=config.center_lon + dlon,
        )


def _iter_patients(config: SeedConfig) -> Iterable[PatientDB]:
    for _ in range(config.patients):
        dlat, dlon = _random_offset_degrees(config.spread_km)
        registered_at = datetime.now(UTC) - timedelta(minutes=random.randint(0, 90))
        yield PatientDB(
            lat=config.center_lat + dlat,
            lon=config.center_lon + dlon,
            time_to_hospital_minutes=random.randint(10, 60),
            registered_at=registered_at,
        )


def _iter_ambulances(config: SeedConfig) -> Iterable[AmbulanceDB]:
    for _ in range(config.ambulances):
        dlat, dlon = _random_offset_degrees(config.spread_km)
        yield AmbulanceDB(
            lat=config.center_lat + dlat,
            lon=config.center_lon + dlon,
            assigned_patient_id=None,
        )


async def _seed(session: AsyncSession, config: SeedConfig) -> None:
    if config.wipe:
        await session.execute(delete(AmbulanceDB))
        await session.execute(delete(PatientDB))
        await session.execute(delete(HospitalDB))

    session.add_all(list(_iter_hospitals(config)))
    session.add_all(list(_iter_patients(config)))
    session.add_all(list(_iter_ambulances(config)))

    await session.commit()


def _parse_args() -> SeedConfig:
    parser = argparse.ArgumentParser(description="Seed demo data for hospitopt.")
    parser.add_argument("--hospitals", type=int, default=1)
    parser.add_argument("--patients", type=int, default=30)
    parser.add_argument("--ambulances", type=int, default=20)
    (parser.add_argument("--center-lat", type=float, default=38.946),)
    parser.add_argument("--center-lon", type=float, default=-9.331)
    parser.add_argument("--spread-km", type=float, default=5.0)
    parser.add_argument("--no-wipe", action="store_false", dest="wipe", help="Keep existing rows.")
    parser.set_defaults(wipe=True)
    args = parser.parse_args()

    return SeedConfig(
        hospitals=args.hospitals,
        patients=args.patients,
        ambulances=args.ambulances,
        center_lat=args.center_lat,
        center_lon=args.center_lon,
        spread_km=args.spread_km,
        wipe=args.wipe,
    )


async def main() -> None:
    env = Environment()
    app_config = WorkerConfig.from_yaml(env.CONFIG_FILE_PATH)
    db_url = app_config.ingestion.connection_string()

    engine = create_async_engine(db_url, pool_pre_ping=True)
    async_session_factory = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    config = _parse_args()
    async with async_session_factory() as session:
        await _seed(session, config)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
