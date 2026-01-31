"""FastAPI app for serving optimization results."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine

from hospitopt_api.routes import ambulances, assignments, health, hospitals, patients
from hospitopt_core.config.env import Environment
from hospitopt_core.config.settings import AppConfig

env = Environment()
config = AppConfig.from_yaml(env.CONFIG_FILE_PATH)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage app lifespan - setup and teardown."""
    config.logging.setup_logging(level=env.LOG_LEVEL)

    engine, session_factory = config.worker.db_connection.to_engine_session_factory()
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
    allow_origins=[str(origin) for origin in config.api.cors.allow_origins],
    allow_credentials=config.api.cors.allow_credentials,
    allow_methods=config.api.cors.allow_methods,
    allow_headers=config.api.cors.allow_headers,
)

# Register routers
app.include_router(health.router)
app.include_router(hospitals.router)
app.include_router(patients.router)
app.include_router(ambulances.router)
app.include_router(assignments.router)
