"""Integration tests for AG-UI agent endpoints."""

import json

import pytest
from httpx import AsyncClient
from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from pydantic import SecretStr

from hospitopt_api.agent import create_chat_agent, create_sitrep_agent
from hospitopt_api.settings import DEFAULT_CHAT_PROMPT, DEFAULT_SITREP_PROMPT, AgentConfig

models.ALLOW_MODEL_REQUESTS = False

_MINIMAL_RUN_INPUT = {
    "threadId": "t-1",
    "runId": "r-1",
    "state": None,
    "messages": [{"role": "user", "content": "Give me a SITREP", "id": "m-1"}],
    "tools": [],
    "context": [],
    "forwardedProps": {},
}


@pytest.fixture()
def _override_agents(fastapi_app):
    """Replace both agents on app.state with TestModel-backed versions."""
    sitrep = create_sitrep_agent(AgentConfig(system_prompt=DEFAULT_SITREP_PROMPT, api_key=SecretStr("test-key")))
    chat = create_chat_agent(AgentConfig(system_prompt=DEFAULT_CHAT_PROMPT, api_key=SecretStr("test-key")))

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
async def test_sitrep_endpoint_streams_sse(async_client: AsyncClient, _override_agents):
    """POST /agents/sitrep should return an SSE stream with ag-ui events."""
    response = await async_client.post(
        "/agents/sitrep",
        json=_MINIMAL_RUN_INPUT,
        headers={"accept": "text/event-stream"},
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    body = response.text
    assert "RUN_STARTED" in body
    assert "RUN_FINISHED" in body


@pytest.mark.asyncio
async def test_chat_endpoint_streams_sse(async_client: AsyncClient, _override_agents):
    """POST /agents/chat should return an SSE stream with ag-ui events."""
    chat_input = {
        **_MINIMAL_RUN_INPUT,
        "messages": [{"role": "user", "content": "What is deadline slack?", "id": "m-2"}],
    }

    response = await async_client.post(
        "/agents/chat",
        json=chat_input,
        headers={"accept": "text/event-stream"},
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    body = response.text
    assert "RUN_STARTED" in body
    assert "RUN_FINISHED" in body


@pytest.mark.asyncio
async def test_sitrep_endpoint_returns_parseable_events(async_client: AsyncClient, _override_agents):
    """Each SSE data line should be valid JSON with a 'type' field."""
    response = await async_client.post(
        "/agents/sitrep",
        json=_MINIMAL_RUN_INPUT,
        headers={"accept": "text/event-stream"},
    )

    event_types = set()
    for line in response.text.splitlines():
        if line.startswith("data: "):
            payload = json.loads(line.removeprefix("data: "))
            assert "type" in payload
            event_types.add(payload["type"])

    assert "RUN_STARTED" in event_types
    assert "RUN_FINISHED" in event_types
