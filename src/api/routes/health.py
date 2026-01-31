from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from api.dependencies import get_session

router = APIRouter()


@router.get("/")
async def root(request: Request) -> Any:
    user_agent = request.headers.get("user-agent", "").lower()
    if any(browser in user_agent for browser in ("mozilla", "chrome", "safari", "edge")):
        return RedirectResponse(url="/docs")
    return {"message": "HospitOPT API is running. Visit /docs for API documentation."}


@router.get("/health", tags=["Health"])
async def health(session: AsyncSession = Depends(get_session)) -> JSONResponse:
    """
    Comprehensive health check endpoint.

    Checks:
    - API responsiveness
    - Database connectivity

    Returns 200 if all checks pass, 503 if any check fails.
    """
    checks = {"api": "healthy", "database": "unknown"}

    # Check database connectivity
    try:
        result = await session.execute(text("SELECT 1"))
        if result:
            checks["database"] = "healthy"
    except SQLAlchemyError as e:
        checks["database"] = f"unhealthy: {str(e)}"
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "checks": checks},
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "healthy", "checks": checks},
    )


@router.get("/health/live", tags=["Health"])
async def liveness() -> dict:
    """
    Liveness probe endpoint.

    Indicates whether the application is running.
    This endpoint should always return 200 if the app is alive.
    """
    return {"status": "alive"}
