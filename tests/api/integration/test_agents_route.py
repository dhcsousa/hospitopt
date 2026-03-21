"""Integration tests for agent endpoints."""

import pytest
from httpx import AsyncClient
from pydantic_ai import models
from pydantic_ai.models.test import TestModel


from hospitopt_api.agent import create_chat_agent, create_sitrep_agent
from hospitopt_api.settings import DEFAULT_CHAT_PROMPT, DEFAULT_SITREP_PROMPT, AgentConfig

models.ALLOW_MODEL_REQUESTS = False

_MINIMAL_CHAT_INPUT = {
    "threadId": "t-1",
    "runId": "r-1",
    "state": None,
    "messages": [{"role": "user", "content": "What is deadline slack?", "id": "m-1"}],
    "tools": [],
    "context": [],
    "forwardedProps": {},
}


@pytest.fixture()
def _override_agents(fastapi_app):
    """Replace both agents on app.state with TestModel-backed versions."""
    sitrep = create_sitrep_agent(
        AgentConfig(model="test-model", base_url="http://localhost:11434/v1", system_prompt=DEFAULT_SITREP_PROMPT)
    )
    chat = create_chat_agent(
        AgentConfig(model="test-model", base_url="http://localhost:11434/v1", system_prompt=DEFAULT_CHAT_PROMPT)
    )

    # Use call_tools=[] so sitrep tools don't hit the DB — we're testing the route layer.
    ctx_s = sitrep.override(model=TestModel(call_tools=[]))
    ctx_c = chat.override(model=TestModel())
    ctx_s.__enter__()
    ctx_c.__enter__()

    fastapi_app.state.sitrep_agent = sitrep
    fastapi_app.state.chat_agent = chat
    yield
    ctx_c.__exit__(None, None, None)
    ctx_s.__exit__(None, None, None)


@pytest.mark.asyncio
async def test_sitrep_endpoint_returns_structured_json(async_client: AsyncClient, _override_agents):
    """POST /agents/sitrep should return a JSON SitrepReport."""
    response = await async_client.post("/agents/sitrep")

    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]

    data = response.json()
    for key in (
        "patient_overview",
        "hospital_capacity",
        "ambulance_fleet_status",
        "critical_patients",
        "unassigned_patients",
        "action_required",
        "summary",
    ):
        assert key in data


@pytest.mark.asyncio
async def test_chat_endpoint_streams_sse(async_client: AsyncClient, _override_agents):
    """POST /agents/chat should return an SSE stream with ag-ui events."""
    response = await async_client.post(
        "/agents/chat",
        json=_MINIMAL_CHAT_INPUT,
        headers={"accept": "text/event-stream"},
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    body = response.text
    assert "RUN_STARTED" in body
    assert "RUN_FINISHED" in body
