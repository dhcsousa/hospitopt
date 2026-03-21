"""Integration tests for agent tools (require real DB via testcontainers)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic_ai import models
from pydantic_ai.models.test import TestModel
from sqlalchemy import delete


from hospitopt_api.agent import SITREPDeps, create_sitrep_agent
from hospitopt_api.models import SitrepReport
from hospitopt_api.settings import AgentConfig, DEFAULT_SITREP_PROMPT
from hospitopt_core.db.models import AmbulanceDB, HospitalDB, PatientAssignmentDB, PatientDB

models.ALLOW_MODEL_REQUESTS = False


def _sitrep_config() -> AgentConfig:
    return AgentConfig(
        model="test-model",
        base_url="http://localhost:11434/v1",
        system_prompt=DEFAULT_SITREP_PROMPT,
    )


@pytest.mark.asyncio
async def test_sitrep_agent_empty_db(session_factory):
    """On an empty DB the agent should still run and call all tools."""
    agent = create_sitrep_agent(_sitrep_config())
    deps = SITREPDeps(session_factory=session_factory)

    with agent.override(model=TestModel(call_tools="all")):
        result = await agent.run("Give me a SITREP", deps=deps)

    assert isinstance(result.output, SitrepReport)


@pytest.mark.asyncio
async def test_sitrep_agent_with_data(async_session, session_factory):
    """Seed data and verify the agent calls tools that hit every DB table."""
    now = datetime.now(UTC)
    h_id = uuid4()
    p_id = uuid4()
    a_id = uuid4()

    async_session.add(HospitalDB(id=h_id, name="H1", bed_capacity=10, used_beds=9, lat=0, lon=0))
    async_session.add(PatientDB(id=p_id, lat=0, lon=0, time_to_hospital_minutes=30, registered_at=now))
    async_session.add(AmbulanceDB(id=a_id, lat=0, lon=0, assigned_patient_id=p_id))
    async_session.add(
        PatientAssignmentDB(
            patient_id=p_id,
            hospital_id=h_id,
            ambulance_id=a_id,
            treatment_deadline_minutes=30,
            deadline_slack_minutes=3,
            patient_registered_at=now,
            requires_urgent_transport=True,
        )
    )
    await async_session.commit()

    agent = create_sitrep_agent(_sitrep_config())
    deps = SITREPDeps(session_factory=session_factory)

    with agent.override(model=TestModel(call_tools="all")):
        result = await agent.run("Give me a SITREP", deps=deps)

    assert isinstance(result.output, SitrepReport)

    # Clean up committed rows so subsequent tests start with a clean DB.
    await async_session.execute(delete(PatientAssignmentDB))
    await async_session.execute(delete(AmbulanceDB))
    await async_session.execute(delete(PatientDB))
    await async_session.execute(delete(HospitalDB))
    await async_session.commit()
