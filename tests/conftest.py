"""Pytest configuration and fixtures for hospitopt tests."""

from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from testcontainers.core.exceptions import ContainerStartException
from testcontainers.postgres import PostgresContainer

from hospitopt_core.config.settings import DbConnectionConfig
from hospitopt_core.db.models import (
    Base,
)


@pytest_asyncio.fixture(scope="session")
async def postgres_container() -> AsyncGenerator[PostgresContainer, None]:
    """Start Postgres container for database tests."""
    try:
        with PostgresContainer("postgres:18-alpine") as postgres:
            yield postgres
    except ContainerStartException as e:
        pytest.skip(f"Failed to start Postgres container: {e}")


@pytest_asyncio.fixture(scope="session")
async def async_engine(postgres_container):
    """Create async SQLAlchemy engine with test database."""
    cfg = DbConnectionConfig(
        host=postgres_container.get_container_host_ip(),
        database=postgres_container.dbname,
        user=postgres_container.username,
        password=SecretStr(postgres_container.password),
        port=postgres_container.get_exposed_port(5432),
    )
    engine = create_async_engine(
        cfg.connection_string(),
        poolclass=NullPool,  # Prevent connection reuse across tests
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture(scope="session")
def session_factory(async_engine):
    """Create session factory for database access."""
    return sessionmaker(
        bind=async_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        class_=AsyncSession,
    )


@pytest_asyncio.fixture(scope="function")
async def async_session(session_factory) -> AsyncGenerator[AsyncSession, None]:
    """Get a fresh database session for each test."""
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="session")
def test_api_key() -> str:
    """Test API key for authentication."""
    return "test-api-key-12345"


@pytest_asyncio.fixture(scope="session")
async def fastapi_app(async_engine, session_factory, test_api_key):
    """Create FastAPI app with test configuration."""
    from unittest.mock import MagicMock

    from hospitopt_core.config.settings import APIConfig, AppConfig, CorsConfig

    # Import after creating engine to avoid circular dependency
    from hospitopt_api.main import app

    # Mock config
    mock_config = MagicMock(spec=AppConfig)
    mock_config.api = APIConfig(
        api_key=SecretStr(test_api_key),
        cors=CorsConfig(
            allow_origins=["http://localhost:3000"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        ),
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


@pytest.fixture(scope="session")
def anyio_backend():
    """Configure asyncio backend for pytest-asyncio."""
    return "asyncio"
