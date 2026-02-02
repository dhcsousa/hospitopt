from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from hospitopt_core.db.models import PatientAssignmentDB
from hospitopt_core.domain.models import OptimizationResult, PatientAssignment
from hospitopt_worker.db import DatabaseWriter, check_connection


@pytest.mark.asyncio
async def test_check_connection_success(session_factory):
    """Test database connection check succeeds."""
    # Should not raise
    await check_connection(session_factory)


@pytest.mark.asyncio
async def test_database_writer_write_empty_result(session_factory):
    """Test writing empty optimization result does nothing."""
    writer = DatabaseWriter(session_factory)
    result = OptimizationResult(
        max_lives_saved=0,
        assignments=[],
        unassigned_patient_ids=[],
    )

    # Should not raise
    await writer.write_optimization_result(result)


@pytest.mark.asyncio
async def test_database_writer_write_new_assignments(session_factory, async_session: AsyncSession):
    """Test writing new patient assignments."""
    writer = DatabaseWriter(session_factory)

    patient_id = uuid4()
    hospital_id = uuid4()
    ambulance_id = uuid4()

    assignments = [
        PatientAssignment(
            patient_id=patient_id,
            hospital_id=hospital_id,
            ambulance_id=ambulance_id,
            estimated_travel_minutes=15,
            deadline_slack_minutes=10,
            treatment_deadline_minutes=30,
            patient_registered_at=datetime.now(UTC),
            requires_urgent_transport=False,
            optimized_at=datetime.now(UTC),
        )
    ]

    result = OptimizationResult(
        max_lives_saved=1,
        assignments=assignments,
        unassigned_patient_ids=[],
    )

    await writer.write_optimization_result(result)

    # Verify assignment was written
    from sqlalchemy import select

    stmt = select(PatientAssignmentDB).where(PatientAssignmentDB.patient_id == patient_id)
    db_result = await async_session.execute(stmt)
    db_assignment = db_result.scalar_one_or_none()

    assert db_assignment is not None
    assert db_assignment.patient_id == patient_id
    assert db_assignment.hospital_id == hospital_id
    assert db_assignment.ambulance_id == ambulance_id
    assert db_assignment.estimated_travel_minutes == 15
    assert db_assignment.deadline_slack_minutes == 10


@pytest.mark.asyncio
async def test_database_writer_replaces_existing_assignments(session_factory, async_session: AsyncSession):
    """Test that writing assignments replaces existing ones for the same patients."""
    writer = DatabaseWriter(session_factory)

    patient_id = uuid4()
    hospital_id_1 = uuid4()
    hospital_id_2 = uuid4()
    ambulance_id = uuid4()

    # Write first assignment
    assignment_1 = PatientAssignment(
        patient_id=patient_id,
        hospital_id=hospital_id_1,
        ambulance_id=ambulance_id,
        estimated_travel_minutes=15,
        deadline_slack_minutes=10,
        treatment_deadline_minutes=30,
        patient_registered_at=datetime.now(UTC),
        requires_urgent_transport=False,
        optimized_at=datetime.now(UTC),
    )

    result_1 = OptimizationResult(
        max_lives_saved=1,
        assignments=[assignment_1],
        unassigned_patient_ids=[],
    )

    await writer.write_optimization_result(result_1)

    # Write second assignment for same patient (different hospital)
    assignment_2 = PatientAssignment(
        patient_id=patient_id,
        hospital_id=hospital_id_2,
        ambulance_id=ambulance_id,
        estimated_travel_minutes=20,
        deadline_slack_minutes=5,
        treatment_deadline_minutes=30,
        patient_registered_at=datetime.now(UTC),
        requires_urgent_transport=True,
        optimized_at=datetime.now(UTC),
    )

    result_2 = OptimizationResult(
        max_lives_saved=1,
        assignments=[assignment_2],
        unassigned_patient_ids=[],
    )

    await writer.write_optimization_result(result_2)

    # Verify only the second assignment exists
    from sqlalchemy import select

    stmt = select(PatientAssignmentDB).where(PatientAssignmentDB.patient_id == patient_id)
    db_result = await async_session.execute(stmt)
    db_assignments = db_result.scalars().all()

    assert len(db_assignments) == 1
    assert db_assignments[0].hospital_id == hospital_id_2
    assert db_assignments[0].estimated_travel_minutes == 20
    assert db_assignments[0].requires_urgent_transport is True


@pytest.mark.asyncio
async def test_database_writer_multiple_patients(session_factory, async_session: AsyncSession):
    """Test writing assignments for multiple patients."""
    writer = DatabaseWriter(session_factory)

    patient_ids = [uuid4() for _ in range(3)]
    hospital_id = uuid4()
    ambulance_ids = [uuid4() for _ in range(3)]

    assignments = [
        PatientAssignment(
            patient_id=patient_id,
            hospital_id=hospital_id,
            ambulance_id=ambulance_id,
            estimated_travel_minutes=15 + i,
            deadline_slack_minutes=10,
            treatment_deadline_minutes=30,
            patient_registered_at=datetime.now(UTC),
            requires_urgent_transport=i % 2 == 0,
            optimized_at=datetime.now(UTC),
        )
        for i, (patient_id, ambulance_id) in enumerate(zip(patient_ids, ambulance_ids))
    ]

    result = OptimizationResult(
        max_lives_saved=3,
        assignments=assignments,
        unassigned_patient_ids=[],
    )

    await writer.write_optimization_result(result)

    # Verify all assignments were written
    from sqlalchemy import select

    stmt = select(PatientAssignmentDB).where(PatientAssignmentDB.patient_id.in_(patient_ids))
    db_result = await async_session.execute(stmt)
    db_assignments = db_result.scalars().all()

    assert len(db_assignments) == 3

    # Verify they have different travel times
    travel_times = sorted([a.estimated_travel_minutes for a in db_assignments])
    assert travel_times == [15, 16, 17]
