"""Ingestion interfaces for the worker runtime."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from hospitopt_core.domain.models import Ambulance, Hospital, Patient


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
