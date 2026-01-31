"""Ambulance endpoints."""

from fastapi import APIRouter, Depends, Query, Security
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_session, verify_api_key
from api.models import AmbulancesPage
from core.db.models import AmbulanceDB
from core.domain.models import Ambulance

router = APIRouter(tags=["Resources"])


@router.get("/ambulances", response_model=AmbulancesPage)
async def get_ambulances(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    _: str = Security(verify_api_key),
) -> AmbulancesPage:
    """Get paginated list of ambulances."""
    total = await session.scalar(select(func.count()).select_from(AmbulanceDB))
    result = await session.execute(select(AmbulanceDB).offset(offset).limit(limit))
    ambulances = [
        Ambulance(
            id=row.id,
            lat=row.lat,
            lon=row.lon,
            assigned_patient_id=row.assigned_patient_id,
        )
        for row in result.scalars().all()
    ]
    return AmbulancesPage(items=ambulances, total=total or 0, limit=limit, offset=offset)
