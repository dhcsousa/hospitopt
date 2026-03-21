"""AG-UI protocol endpoints for the SITREP and Chat agents."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ag_ui.core import RunAgentInput
from pydantic_ai.ag_ui import SSE_CONTENT_TYPE, run_ag_ui

from hospitopt_api.agent import AgentDeps
from hospitopt_api.dependencies import get_session

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.post("/sitrep")
async def run_sitrep_agent(
    request: Request,
    run_input: RunAgentInput,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Run the SITREP agent. Streams ag-ui events over SSE."""
    accept = request.headers.get("accept", SSE_CONTENT_TYPE)
    agent = request.app.state.sitrep_agent
    deps = AgentDeps(session=session)

    return StreamingResponse(
        run_ag_ui(agent, run_input, accept=accept, deps=deps),
        media_type=accept,
    )


@router.post("/chat")
async def run_chat_agent(
    request: Request,
    run_input: RunAgentInput,
) -> StreamingResponse:
    """Run the Q&A chat agent. Streams ag-ui events over SSE."""
    accept = request.headers.get("accept", SSE_CONTENT_TYPE)
    agent = request.app.state.chat_agent

    return StreamingResponse(
        run_ag_ui(agent, run_input, accept=accept),
        media_type=accept,
    )
