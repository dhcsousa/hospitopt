"""Hospital endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hospitopt_api.dependencies import get_session
from hospitopt_api.models import HospitalsPage
from hospitopt_core.db.models import HospitalDB
from hospitopt_core.domain.models import Hospital

router = APIRouter(tags=["Resources"])


@router.get("/hospitals", response_model=HospitalsPage)
async def get_hospitals(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> HospitalsPage:
    """Get paginated list of hospitals."""
    total = await session.scalar(select(func.count()).select_from(HospitalDB))
    result = await session.execute(select(HospitalDB).offset(offset).limit(limit))
    hospitals = [
        Hospital(
            id=row.id,
            name=row.name,
            bed_capacity=row.bed_capacity,
            used_beds=row.used_beds,
            lat=row.lat,
            lon=row.lon,
        )
        for row in result.scalars().all()
    ]
    return HospitalsPage(items=hospitals, total=total or 0, limit=limit, offset=offset)
