from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from hospitopt_core.db.models import AmbulanceDB, HospitalDB, PatientAssignmentDB, PatientDB
from hospitopt_core.domain.models import Ambulance, Hospital, OptimizationResult, Patient, PatientAssignment
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


@pytest.mark.asyncio
async def test_write_inputs_persists_all_entities(session_factory, async_session: AsyncSession):
    """Test that hospitals, patients and ambulances are written to their tables."""
    writer = DatabaseWriter(session_factory)

    hospital = Hospital(name="Central", bed_capacity=10, used_beds=3, lat=52.0, lon=4.0)
    patient = Patient(name="Alice", lat=52.1, lon=4.1, time_to_hospital_minutes=30)
    ambulance = Ambulance(lat=52.2, lon=4.2)

    await writer.write_inputs([hospital], [patient], [ambulance])

    from sqlalchemy import select

    h_row = (await async_session.execute(select(HospitalDB).where(HospitalDB.id == hospital.id))).scalar_one()
    assert h_row.name == "Central"
    assert h_row.bed_capacity == 10
    assert h_row.used_beds == 3
    assert h_row.lat == pytest.approx(52.0)

    p_row = (await async_session.execute(select(PatientDB).where(PatientDB.id == patient.id))).scalar_one()
    assert p_row.name == "Alice"
    assert p_row.time_to_hospital_minutes == 30
    assert p_row.status == "waiting"

    a_row = (await async_session.execute(select(AmbulanceDB).where(AmbulanceDB.id == ambulance.id))).scalar_one()
    assert a_row.lat == pytest.approx(52.2)
    assert a_row.assigned_patient_id is None


@pytest.mark.asyncio
async def test_write_inputs_replaces_previous_data(session_factory, async_session: AsyncSession):
    """Calling write_inputs a second time fully replaces the previous set."""
    writer = DatabaseWriter(session_factory)

    h1 = Hospital(name="Old", bed_capacity=5, used_beds=0, lat=1.0, lon=1.0)
    await writer.write_inputs([h1], [], [])

    h2 = Hospital(name="New", bed_capacity=20, used_beds=1, lat=2.0, lon=2.0)
    await writer.write_inputs([h2], [], [])

    from sqlalchemy import select

    rows = (await async_session.execute(select(HospitalDB))).scalars().all()
    assert len(rows) == 1
    assert rows[0].id == h2.id
    assert rows[0].name == "New"


@pytest.mark.asyncio
async def test_write_inputs_empty_lists(session_factory, async_session: AsyncSession):
    """Writing empty lists clears all existing rows."""
    writer = DatabaseWriter(session_factory)

    # Seed some data first
    await writer.write_inputs(
        [Hospital(name="H", bed_capacity=1, used_beds=0, lat=0.0, lon=0.0)],
        [Patient(lat=0.0, lon=0.0, time_to_hospital_minutes=10)],
        [Ambulance(lat=0.0, lon=0.0)],
    )

    # Now write empty
    await writer.write_inputs([], [], [])

    from sqlalchemy import func, select

    assert (await async_session.execute(select(func.count()).select_from(HospitalDB))).scalar() == 0
    assert (await async_session.execute(select(func.count()).select_from(PatientDB))).scalar() == 0
    assert (await async_session.execute(select(func.count()).select_from(AmbulanceDB))).scalar() == 0


@pytest.mark.asyncio
async def test_read_locked_hospitals_returns_mapping(session_factory):
    """Returns {patient_id: hospital_id} for patients with existing assignments."""
    writer = DatabaseWriter(session_factory)

    pid1 = uuid4()
    pid2 = uuid4()
    hid1 = uuid4()
    hid2 = uuid4()

    await writer.write_optimization_result(
        OptimizationResult(
            max_lives_saved=2,
            assignments=[
                PatientAssignment(
                    patient_id=pid1,
                    hospital_id=hid1,
                    treatment_deadline_minutes=20,
                    patient_registered_at=datetime.now(UTC),
                ),
                PatientAssignment(
                    patient_id=pid2,
                    hospital_id=hid2,
                    treatment_deadline_minutes=20,
                    patient_registered_at=datetime.now(UTC),
                ),
            ],
            unassigned_patient_ids=[],
        )
    )

    result = await writer.read_locked_hospitals({pid1, pid2})

    assert result == {pid1: hid1, pid2: hid2}


@pytest.mark.asyncio
async def test_read_locked_hospitals_empty_set(session_factory):
    """Passing an empty set returns an empty dict without querying."""
    writer = DatabaseWriter(session_factory)
    assert await writer.read_locked_hospitals(set()) == {}


@pytest.mark.asyncio
async def test_read_locked_hospitals_ignores_null_hospital(session_factory):
    """Assignments with hospital_id=None are excluded from the result."""
    writer = DatabaseWriter(session_factory)

    pid = uuid4()

    await writer.write_optimization_result(
        OptimizationResult(
            max_lives_saved=1,
            assignments=[
                PatientAssignment(
                    patient_id=pid,
                    hospital_id=None,
                    treatment_deadline_minutes=20,
                    patient_registered_at=datetime.now(UTC),
                ),
            ],
            unassigned_patient_ids=[],
        )
    )

    result = await writer.read_locked_hospitals({pid})
    assert result == {}


@pytest.mark.asyncio
async def test_read_locked_hospitals_only_requested_ids(session_factory):
    """Only returns mappings for the requested patient IDs."""
    writer = DatabaseWriter(session_factory)

    pid_requested = uuid4()
    pid_other = uuid4()
    hid = uuid4()

    await writer.write_optimization_result(
        OptimizationResult(
            max_lives_saved=2,
            assignments=[
                PatientAssignment(
                    patient_id=pid_requested,
                    hospital_id=hid,
                    treatment_deadline_minutes=20,
                    patient_registered_at=datetime.now(UTC),
                ),
                PatientAssignment(
                    patient_id=pid_other,
                    hospital_id=uuid4(),
                    treatment_deadline_minutes=20,
                    patient_registered_at=datetime.now(UTC),
                ),
            ],
            unassigned_patient_ids=[],
        )
    )

    result = await writer.read_locked_hospitals({pid_requested})
    assert result == {pid_requested: hid}
