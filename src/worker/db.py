"""Database access for the worker."""

from datetime import UTC, datetime
from typing import Callable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import AsyncContextManager

from core.db.models import PatientAssignmentDB
from core.domain.models import OptimizationResult


SessionFactory = Callable[[], AsyncContextManager[AsyncSession, None]]


class DatabaseWriter:
    """Write optimization results back to the database."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def write_optimization_result(self, result: OptimizationResult) -> None:
        if not result.assignments:
            return

        patient_ids = [assignment.patient_id for assignment in result.assignments]
        now = datetime.now(UTC)
        insert_rows = [
            PatientAssignmentDB(
                patient_id=assignment.patient_id,
                hospital_id=assignment.hospital_id,
                ambulance_id=assignment.ambulance_id,
                estimated_travel_minutes=assignment.estimated_travel_minutes,
                deadline_slack_minutes=assignment.deadline_slack_minutes,
                treatment_deadline_minutes=assignment.treatment_deadline_minutes,
                patient_registered_at=assignment.patient_registered_at,
                requires_urgent_transport=assignment.requires_urgent_transport,
                optimized_at=now,
            )
            for assignment in result.assignments
        ]

        async with self._session_factory() as session:
            await session.execute(delete(PatientAssignmentDB).where(PatientAssignmentDB.patient_id.in_(patient_ids)))
            session.add_all(insert_rows)
            await session.commit()


async def check_connection(session_factory: SessionFactory) -> None:
    """Sanity check the database connection."""
    async with session_factory() as session:
        await session.execute(select(1))
