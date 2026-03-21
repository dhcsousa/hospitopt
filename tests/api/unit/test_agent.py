"""Unit tests for agent factory functions."""

import pytest
from pydantic_ai import models
from pydantic_ai.models.test import TestModel


from hospitopt_api.agent import create_chat_agent, create_sitrep_agent
from hospitopt_api.settings import AgentConfig, DEFAULT_CHAT_PROMPT, DEFAULT_SITREP_PROMPT

models.ALLOW_MODEL_REQUESTS = False


def _sitrep_config() -> AgentConfig:
    return AgentConfig(
        model="test-model",
        base_url="http://localhost:11434/v1",
        system_prompt=DEFAULT_SITREP_PROMPT,
    )


def _chat_config() -> AgentConfig:
    return AgentConfig(
        model="test-model",
        base_url="http://localhost:11434/v1",
        system_prompt=DEFAULT_CHAT_PROMPT,
    )


def test_create_sitrep_agent_returns_agent():
    agent = create_sitrep_agent(_sitrep_config())
    tool_names = set(agent._function_toolset.tools.keys())
    assert tool_names == {
        "get_situation_summary",
        "get_hospitals_near_capacity",
        "get_critical_patients",
        "get_unassigned_patients",
        "get_ambulance_utilization",
    }


def test_create_chat_agent_returns_agent():
    agent = create_chat_agent(_chat_config())
    assert agent._function_toolset.tools == {}


@pytest.mark.asyncio
async def test_chat_agent_responds():
    agent = create_chat_agent(_chat_config())

    with agent.override(model=TestModel()):
        result = await agent.run("What does deadline slack mean?")

    assert isinstance(result.output, str)
