"""Pytest fixtures for API package tests."""

from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from hospitopt_api.settings import APIConfig, CorsConfig


@pytest.fixture(scope="session")
def test_api_key() -> str:
    """Test API key for authentication."""
    return "test-api-key-12345"


@pytest_asyncio.fixture(scope="session")
async def fastapi_app(async_engine, session_factory, test_api_key):
    """Create FastAPI app with test configuration."""
    from unittest.mock import MagicMock

    from hospitopt_api.main import app

    # Mock config
    mock_config = MagicMock(spec=APIConfig)
    mock_config.api_key = SecretStr(test_api_key)
    mock_config.cors = CorsConfig(
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Set up app state
    app.state.engine = async_engine
    app.state.session_factory = session_factory
    app.state.config = mock_config

    yield app

    # Cleanup
    await async_engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_client(fastapi_app, test_api_key) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for API testing with authentication."""
    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {test_api_key}"},
    ) as client:
        yield client


@pytest_asyncio.fixture(scope="function")
async def unauthorized_client(fastapi_app) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client without authentication."""
    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app),
        base_url="http://test",
    ) as client:
        yield client
