"""FastAPI app for serving optimization results."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from core.config.env import Environment
from core.config.settings import AppConfig
from core.db.models import PatientAssignmentDB
from core.domain.models import PatientAssignment


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    env = Environment()
    config = AppConfig.from_yaml(env.CONFIG_FILE_PATH)
    config.logging.setup_logging(level=env.LOG_LEVEL)

    engine, session_factory = config.worker.db_connection.to_engine_session_factory()
    app.state.engine = engine
    app.state.session_factory = session_factory
    try:
        yield
    finally:
        app_engine: AsyncEngine = app.state.engine
        await app_engine.dispose()


app = FastAPI(title="hospitopt-api", lifespan=lifespan)


async def get_session() -> AsyncIterator[AsyncSession]:
    session_factory = app.state.session_factory
    async with session_factory() as session:
        yield session


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/results", response_model=list[PatientAssignment])
async def get_results(session: AsyncSession = Depends(get_session)) -> list[PatientAssignment]:
    result = await session.execute(select(PatientAssignmentDB).order_by(PatientAssignmentDB.optimized_at.desc()))
    rows = list(result.scalars().all())

    assignments = [
        PatientAssignment(
            patient_id=row.patient_id,
            hospital_id=row.hospital_id,
            ambulance_id=row.ambulance_id,
            estimated_travel_minutes=row.estimated_travel_minutes,
            deadline_slack_minutes=row.deadline_slack_minutes,
            treatment_deadline_minutes=row.treatment_deadline_minutes,
            patient_registered_at=row.patient_registered_at,
            requires_urgent_transport=row.requires_urgent_transport,
            optimized_at=row.optimized_at,
        )
        for row in rows
    ]

    return assignments
