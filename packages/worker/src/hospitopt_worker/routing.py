"""Routing backend abstraction for travel-time matrix computation."""

from abc import ABC, abstractmethod

import httpx
from google.maps import routing_v2

from hospitopt_core.domain.models import Ambulance, Hospital, MinutesTables, Patient
from hospitopt_worker.settings import GoogleRoutingConfig, ValhallaRoutingConfig


class RoutingBackend(ABC):
    """Async-context-managed routing backend."""

    @abstractmethod
    async def build_minutes_tables(
        self,
        patients: list[Patient],
        hospitals: list[Hospital],
        ambulances: list[Ambulance],
    ) -> MinutesTables: ...

    async def aclose(self) -> None:
        """Release resources. Override in subclasses that hold clients."""

    async def __aenter__(self) -> RoutingBackend:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    @staticmethod
    def from_config(
        routing_config: GoogleRoutingConfig | ValhallaRoutingConfig,
    ) -> RoutingBackend:
        """Create the appropriate backend from a routing config."""
        if isinstance(routing_config, GoogleRoutingConfig):
            return GoogleRoutingBackend(routing_config)
        if isinstance(routing_config, ValhallaRoutingConfig):
            return ValhallaRoutingBackend(routing_config)
        raise ValueError(f"Unsupported routing backend: {routing_config}")


class GoogleRoutingBackend(RoutingBackend):
    """Google Maps Routes API backend."""

    def __init__(self, config: GoogleRoutingConfig) -> None:
        self._client = routing_v2.RoutesAsyncClient(client_options={"api_key": config.api_key.get_secret_value()})

    async def build_minutes_tables(
        self,
        patients: list[Patient],
        hospitals: list[Hospital],
        ambulances: list[Ambulance],
    ) -> MinutesTables:
        from hospitopt_worker.routes import build_minutes_tables

        return await build_minutes_tables(self._client, patients, hospitals, ambulances)


class ValhallaRoutingBackend(RoutingBackend):
    """Self-hosted Valhalla routing backend."""

    def __init__(self, config: ValhallaRoutingConfig) -> None:
        self._client = httpx.AsyncClient(base_url=str(config.url), timeout=30.0)
        self._costing = config.costing

    async def build_minutes_tables(
        self,
        patients: list[Patient],
        hospitals: list[Hospital],
        ambulances: list[Ambulance],
    ) -> MinutesTables:
        from hospitopt_worker.routes_valhalla import build_minutes_tables

        return await build_minutes_tables(self._client, patients, hospitals, ambulances, costing=self._costing)

    async def aclose(self) -> None:
        await self._client.aclose()
