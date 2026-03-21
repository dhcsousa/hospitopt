"""AG-UI protocol endpoints for the SITREP and Chat agents."""

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ag_ui.core import RunAgentInput
from pydantic_ai.ag_ui import SSE_CONTENT_TYPE, run_ag_ui

from pydantic_ai import Agent

from hospitopt_api.agent import SITREPDeps, ChatDeps
from hospitopt_api.models import ScreenContext, SitrepReport

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.post("/sitrep", response_model=SitrepReport)
async def run_sitrep_agent(request: Request) -> SitrepReport:
    """Run the SITREP agent and return the structured report as JSON."""
    agent: Agent[SITREPDeps, SitrepReport] = request.app.state.sitrep_agent
    deps = SITREPDeps(session_factory=request.app.state.session_factory)

    result = await agent.run(
        "Generate a comprehensive situation report.",
        deps=deps,
    )
    report: SitrepReport = result.output
    return report


@router.post("/chat")
async def run_chat_agent(
    request: Request,
    run_input: RunAgentInput,
) -> StreamingResponse:
    """Run the Q&A chat agent. Streams ag-ui events over SSE."""
    accept = request.headers.get("accept", SSE_CONTENT_TYPE)
    agent = request.app.state.chat_agent

    # Parse frontend context into a typed model and build the prompt.
    ctx_entries = [{"description": c.description, "value": c.value} for c in run_input.context]
    screen = ScreenContext.from_ag_ui(ctx_entries)
    deps = ChatDeps(screen_context=screen)

    return StreamingResponse(
        run_ag_ui(agent, run_input, accept=accept, deps=deps),
        media_type=accept,
    )
