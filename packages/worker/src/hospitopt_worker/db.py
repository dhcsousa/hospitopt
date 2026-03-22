"""Database access for the worker."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Callable
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import AsyncContextManager

from hospitopt_core.db.models import AmbulanceDB, HospitalDB, PatientAssignmentDB, PatientDB
from hospitopt_core.domain.models import Ambulance, Hospital, OptimizationResult, Patient


SessionFactory = Callable[[], AsyncContextManager[AsyncSession, None]]


class DatabaseWriter:
    """Write optimization results back to the database."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def write_inputs(
        self,
        hospitals: Sequence[Hospital],
        patients: Sequence[Patient],
        ambulances: Sequence[Ambulance],
    ) -> None:
        """Persist the current set of hospitals, patients and ambulances."""
        async with self._session_factory() as session:
            await session.execute(delete(HospitalDB))
            await session.execute(delete(PatientDB))
            await session.execute(delete(AmbulanceDB))
            session.add_all(
                HospitalDB(
                    id=h.id,
                    name=h.name,
                    bed_capacity=h.bed_capacity,
                    used_beds=h.used_beds,
                    lat=h.lat,
                    lon=h.lon,
                )
                for h in hospitals
            )
            session.add_all(
                PatientDB(
                    id=p.id,
                    name=p.name,
                    lat=p.lat,
                    lon=p.lon,
                    time_to_hospital_minutes=p.time_to_hospital_minutes,
                    status=p.status,
                    registered_at=p.registered_at,
                )
                for p in patients
            )
            session.add_all(
                AmbulanceDB(
                    id=a.id,
                    lat=a.lat,
                    lon=a.lon,
                    assigned_patient_id=a.assigned_patient_id,
                )
                for a in ambulances
            )
            await session.commit()

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

    async def read_locked_hospitals(self, patient_ids: set[UUID]) -> dict[UUID, UUID]:
        """Return {patient_id: hospital_id} for previously assigned patients."""
        if not patient_ids:
            return {}
        async with self._session_factory() as session:
            stmt = select(PatientAssignmentDB.patient_id, PatientAssignmentDB.hospital_id).where(
                PatientAssignmentDB.patient_id.in_(patient_ids),
                PatientAssignmentDB.hospital_id.is_not(None),
            )
            rows = (await session.execute(stmt)).all()
            return {r.patient_id: r.hospital_id for r in rows}


async def check_connection(session_factory: SessionFactory) -> None:
    """Sanity check the database connection."""
    async with session_factory() as session:
        await session.execute(select(1))
