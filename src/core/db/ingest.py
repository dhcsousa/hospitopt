"""Data ingestion interfaces for hospitals, patients, and ambulances."""

from abc import ABC, abstractmethod
from typing import Callable, Sequence, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import AsyncContextManager

from core.db.models import AmbulanceDB, HospitalDB, PatientDB
from core.domain.models import Ambulance, Hospital, Patient


SessionFactory = Callable[[], AsyncContextManager[AsyncSession, None]]

ModelT = TypeVar("ModelT")


class DataIngestor(ABC):
    """Abstract interface for loading domain data."""

    @abstractmethod
    async def get_hospitals(self) -> Sequence[Hospital]:
        """Return hospitals to be optimized."""
        ...

    @abstractmethod
    async def get_patients(self) -> Sequence[Patient]:
        """Return patients to be optimized."""
        ...

    @abstractmethod
    async def get_ambulances(self) -> Sequence[Ambulance]:
        """Return ambulances to be optimized."""
        ...


class SQLAlchemyIngestor(DataIngestor):
    """SQLAlchemy-backed ingestor for domain data."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def get_hospitals(self) -> Sequence[Hospital]:
        rows: Sequence[HospitalDB] = await self._fetch_rows(select(HospitalDB))
        return [
            Hospital(
                id=row.id,
                name=row.name,
                bed_capacity=row.bed_capacity,
                used_beds=row.used_beds,
                lat=row.lat,
                lon=row.lon,
            )
            for row in rows
        ]

    async def get_patients(self) -> Sequence[Patient]:
        rows: Sequence[PatientDB] = await self._fetch_rows(select(PatientDB))
        return [
            Patient(
                id=row.id,
                lat=row.lat,
                lon=row.lon,
                time_to_hospital_minutes=row.time_to_hospital_minutes,
                registered_at=row.registered_at,
            )
            for row in rows
        ]

    async def get_ambulances(self) -> Sequence[Ambulance]:
        rows: Sequence[AmbulanceDB] = await self._fetch_rows(select(AmbulanceDB))
        return [
            Ambulance(
                id=row.id,
                lat=row.lat,
                lon=row.lon,
                assigned_patient_id=row.assigned_patient_id,
            )
            for row in rows
        ]

    async def _fetch_rows(self, query: Select[ModelT]) -> Sequence[ModelT]:
        async with self._session_factory() as session:
            result = await session.execute(query)
            return list(result.scalars().all())
