"""Shared API dependencies."""

from typing import AsyncIterator

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

bearer_scheme = HTTPBearer()


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
) -> None:
    """Verify the API key matches the configured value."""

    # Access via request context to avoid circular import
    from hospitopt_api.main import app

    config = app.state.config
    if credentials.credentials != config.api.api_key.get_secret_value():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )


async def get_session() -> AsyncIterator[AsyncSession]:
    """Get database session."""
    from hospitopt_api.main import app

    session_factory = app.state.session_factory
    async with session_factory() as session:
        yield session
