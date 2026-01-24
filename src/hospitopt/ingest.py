from abc import ABC, abstractmethod
from typing import Protocol, Sequence

from hospitopt.models import Ambulance, Hospital, Patient


class DataIngestor(ABC):
    @abstractmethod
    async def get_hospitals(self) -> Sequence[Hospital]: ...

    @abstractmethod
    async def get_patients(self) -> Sequence[Patient]: ...

    @abstractmethod
    async def get_ambulances(self) -> Sequence[Ambulance]: ...


class DatabaseClient(Protocol):
    async def fetch_hospitals(self) -> Sequence[Hospital]: ...

    async def fetch_patients(self) -> Sequence[Patient]: ...

    async def fetch_ambulances(self) -> Sequence[Ambulance]: ...


class DatabaseIngestor(DataIngestor):
    def __init__(self, client: DatabaseClient) -> None:
        self._client = client

    async def get_hospitals(self) -> Sequence[Hospital]:
        return await self._client.fetch_hospitals()

    async def get_patients(self) -> Sequence[Patient]:
        return await self._client.fetch_patients()

    async def get_ambulances(self) -> Sequence[Ambulance]:
        return await self._client.fetch_ambulances()
