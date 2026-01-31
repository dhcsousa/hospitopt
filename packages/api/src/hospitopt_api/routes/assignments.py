"""Patient assignment endpoints."""

from fastapi import APIRouter, Depends, Query, Security
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hospitopt_api.dependencies import get_session, verify_api_key
from hospitopt_api.models import AssignmentsPage
from hospitopt_core.db.models import PatientAssignmentDB
from hospitopt_core.domain.models import PatientAssignment

router = APIRouter(tags=["Assignments"])


@router.get("/assignments", response_model=AssignmentsPage)
async def get_assignments(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    _: str = Security(verify_api_key),
) -> AssignmentsPage:
    """Get paginated list of patient assignments."""
    total = await session.scalar(select(func.count()).select_from(PatientAssignmentDB))
    result = await session.execute(
        select(PatientAssignmentDB).order_by(PatientAssignmentDB.optimized_at.desc()).offset(offset).limit(limit)
    )
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
        for row in result.scalars().all()
    ]
    return AssignmentsPage(items=assignments, total=total or 0, limit=limit, offset=offset)
