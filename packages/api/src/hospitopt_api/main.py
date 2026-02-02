"""FastAPI app for serving optimization results."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine

from hospitopt_api.routes import ambulances, assignments, health, hospitals, patients
from hospitopt_core.config.env import Environment

from hospitopt_api.settings import APIConfig

env = Environment()
if not env.API_CONFIG_FILE_PATH:  # pragma: no cover
    raise ValueError("API_CONFIG_FILE_PATH environment variable is not set. For running the API, this must be set.")
config = APIConfig.from_yaml(env.API_CONFIG_FILE_PATH)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # pragma: no cover
    """Manage app lifespan - setup and teardown."""
    config.logging.setup_logging(level=env.LOG_LEVEL)

    engine, session_factory = config.db_connection.to_engine_session_factory()
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.config = config

    try:
        yield
    finally:
        app_engine: AsyncEngine = app.state.engine
        await app_engine.dispose()


app = FastAPI(title="hospitopt-api", lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in config.cors.allow_origins],
    allow_credentials=config.cors.allow_credentials,
    allow_methods=config.cors.allow_methods,
    allow_headers=config.cors.allow_headers,
)

# Register routers
app.include_router(health.router)
app.include_router(hospitals.router)
app.include_router(patients.router)
app.include_router(ambulances.router)
app.include_router(assignments.router)
