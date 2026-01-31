"""Patient endpoints."""

from fastapi import APIRouter, Depends, Query, Security
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hospitopt_api.dependencies import get_session, verify_api_key
from hospitopt_api.models import PatientsPage
from hospitopt_core.db.models import PatientDB
from hospitopt_core.domain.models import Patient

router = APIRouter(tags=["Resources"])


@router.get("/patients", response_model=PatientsPage)
async def get_patients(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    _: str = Security(verify_api_key),
) -> PatientsPage:
    """Get paginated list of patients."""
    total = await session.scalar(select(func.count()).select_from(PatientDB))
    result = await session.execute(select(PatientDB).offset(offset).limit(limit))
    patients = [
        Patient(
            id=row.id,
            lat=row.lat,
            lon=row.lon,
            time_to_hospital_minutes=row.time_to_hospital_minutes,
            registered_at=row.registered_at,
        )
        for row in result.scalars().all()
    ]
    return PatientsPage(items=patients, total=total or 0, limit=limit, offset=offset)
