"""HTTP example ingestion for the worker runtime."""

from collections.abc import Sequence
from typing import TypeVar

from httpx import AsyncClient
from pydantic import HttpUrl, SecretStr

from hospitopt_core.domain.models import Ambulance, Hospital, Patient
from hospitopt_worker.ingestion.base import DataIngestor

ModelT = TypeVar("ModelT")


class APIIngestor(DataIngestor):
    """HTTP-based ingestor for domain data."""

    def __init__(self, host_url: HttpUrl, api_key: SecretStr) -> None:
        headers = {"Authorization": f"Bearer {api_key.get_secret_value()}"}
        self._httpx_async_client = AsyncClient(base_url=str(host_url).rstrip("/"), headers=headers)

    async def get_hospitals(self) -> Sequence[Hospital]:
        response = await self._httpx_async_client.get("/hospitals")
        response.raise_for_status()
        payload = response.json()
        items = payload.get("items", payload)
        return [Hospital.model_validate(item) for item in items]

    async def get_patients(self) -> Sequence[Patient]:
        response = await self._httpx_async_client.get("/patients")
        response.raise_for_status()
        payload = response.json()
        items = payload.get("items", payload)
        return [Patient.model_validate(item) for item in items]

    async def get_ambulances(self) -> Sequence[Ambulance]:
        response = await self._httpx_async_client.get("/ambulances")
        response.raise_for_status()
        payload = response.json()
        items = payload.get("items", payload)
        return [Ambulance.model_validate(item) for item in items]
