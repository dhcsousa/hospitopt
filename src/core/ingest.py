"""Data ingestion interfaces for hospitals, patients, and ambulances."""

from abc import ABC, abstractmethod
from typing import Protocol, Sequence

from core.models import Ambulance, Hospital, Patient


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


class DatabaseClient(Protocol):
    """Protocol for database-backed data access."""

    async def fetch_hospitals(self) -> Sequence[Hospital]: ...

    async def fetch_patients(self) -> Sequence[Patient]: ...

    async def fetch_ambulances(self) -> Sequence[Ambulance]: ...


class DatabaseIngestor(DataIngestor):
    """Data ingestor backed by a DatabaseClient implementation."""

    def __init__(self, client: DatabaseClient) -> None:
        """Initialize with a database client."""
        self._client = client

    async def get_hospitals(self) -> Sequence[Hospital]:
        """Fetch hospitals from the database client."""
        return await self._client.fetch_hospitals()

    async def get_patients(self) -> Sequence[Patient]:
        """Fetch patients from the database client."""
        return await self._client.fetch_patients()

    async def get_ambulances(self) -> Sequence[Ambulance]:
        """Fetch ambulances from the database client."""
        return await self._client.fetch_ambulances()
