"""PydanticAI agents for mass casualty event coordination.

Two agents:
- **sitrep_agent**: Generates structured situation reports from live DB data.
- **chat_agent**: Answers free-form Q&A based on screen context provided by the frontend.
"""

from dataclasses import dataclass

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from hospitopt_api.models import (
    AmbulanceStatusInfo,
    CriticalPatientInfo,
    HospitalCapacityInfo,
    SituationSummary,
    UnassignedPatientInfo,
)
from hospitopt_api.settings import AgentConfig
from hospitopt_core.db.models import (
    AmbulanceDB,
    HospitalDB,
    PatientAssignmentDB,
    PatientDB,
)


@dataclass
class AgentDeps:
    """Dependencies injected into the agent at runtime."""

    session_factory: async_sessionmaker[AsyncSession]


def _make_model(config: AgentConfig) -> OpenAIChatModel:
    provider = OpenAIProvider(
        base_url=config.base_url,
        api_key=config.api_key.get_secret_value() if config.api_key else None,
    )
    return OpenAIChatModel(config.model, provider=provider)


def create_sitrep_agent(config: AgentConfig) -> Agent[AgentDeps, str]:
    """Create the SITREP agent that queries live data and generates situation reports."""
    agent: Agent[AgentDeps, str] = Agent(
        model=_make_model(config),
        system_prompt=config.system_prompt,
        deps_type=AgentDeps,
    )

    @agent.tool
    async def get_situation_summary(ctx: RunContext[AgentDeps]) -> SituationSummary:
        """Get a high-level summary of the current MCE situation: patient counts, hospital capacity, ambulance status."""
        async with ctx.deps.session_factory() as session:
            total_patients = await session.scalar(select(func.count()).select_from(PatientDB)) or 0
            total_hospitals = await session.scalar(select(func.count()).select_from(HospitalDB)) or 0
            total_ambulances = await session.scalar(select(func.count()).select_from(AmbulanceDB)) or 0

            total_beds = await session.scalar(select(func.coalesce(func.sum(HospitalDB.bed_capacity), 0))) or 0
            used_beds = await session.scalar(select(func.coalesce(func.sum(HospitalDB.used_beds), 0))) or 0

            assigned_patients = (
                await session.scalar(
                    select(func.count())
                    .select_from(PatientAssignmentDB)
                    .where(PatientAssignmentDB.hospital_id.is_not(None))
                )
                or 0
            )

            urgent_patients = (
                await session.scalar(
                    select(func.count())
                    .select_from(PatientAssignmentDB)
                    .where(PatientAssignmentDB.requires_urgent_transport.is_(True))
                )
                or 0
            )

            deployed_ambulances = (
                await session.scalar(
                    select(func.count()).select_from(AmbulanceDB).where(AmbulanceDB.assigned_patient_id.is_not(None))
                )
                or 0
            )

        return SituationSummary(
            total_patients=total_patients,
            assigned_patients=assigned_patients,
            unassigned_patients=total_patients - assigned_patients,
            urgent_patients=urgent_patients,
            total_hospitals=total_hospitals,
            total_beds=total_beds,
            used_beds=used_beds,
            available_beds=total_beds - used_beds,
            total_ambulances=total_ambulances,
            deployed_ambulances=deployed_ambulances,
            idle_ambulances=total_ambulances - deployed_ambulances,
        )

    @agent.tool
    async def get_hospitals_near_capacity(
        ctx: RunContext[AgentDeps], threshold_pct: float = 80.0
    ) -> list[HospitalCapacityInfo]:
        """Get hospitals where bed occupancy exceeds the given threshold percentage. Defaults to 80%."""
        async with ctx.deps.session_factory() as session:
            result = await session.execute(select(HospitalDB))
            hospitals = []
            for row in result.scalars().all():
                if row.bed_capacity == 0:
                    continue
                occupancy = (row.used_beds / row.bed_capacity) * 100
                if occupancy >= threshold_pct:
                    hospitals.append(
                        HospitalCapacityInfo(
                            name=row.name,
                            bed_capacity=row.bed_capacity,
                            used_beds=row.used_beds,
                            available_beds=row.bed_capacity - row.used_beds,
                            occupancy_pct=round(occupancy, 1),
                        )
                    )
        hospitals.sort(key=lambda h: h.occupancy_pct, reverse=True)
        return hospitals

    @agent.tool
    async def get_critical_patients(
        ctx: RunContext[AgentDeps], max_slack_minutes: int = 5
    ) -> list[CriticalPatientInfo]:
        """Get patients with deadline slack <= the given threshold (default 5 minutes). These are the most time-critical."""
        async with ctx.deps.session_factory() as session:
            result = await session.execute(
                select(PatientAssignmentDB)
                .where(
                    (PatientAssignmentDB.deadline_slack_minutes.is_not(None))
                    & (PatientAssignmentDB.deadline_slack_minutes <= max_slack_minutes)
                )
                .order_by(PatientAssignmentDB.deadline_slack_minutes.asc())
            )
            return [
                CriticalPatientInfo(
                    patient_id=str(row.patient_id),
                    deadline_slack_minutes=row.deadline_slack_minutes,
                    treatment_deadline_minutes=row.treatment_deadline_minutes,
                    hospital_id=str(row.hospital_id) if row.hospital_id else None,
                    ambulance_id=str(row.ambulance_id) if row.ambulance_id else None,
                    requires_urgent_transport=row.requires_urgent_transport,
                )
                for row in result.scalars().all()
            ]

    @agent.tool
    async def get_unassigned_patients(ctx: RunContext[AgentDeps]) -> list[UnassignedPatientInfo]:
        """Get patients that require urgent transport (no hospital/ambulance assignment — likely need helicopter extraction)."""
        async with ctx.deps.session_factory() as session:
            result = await session.execute(
                select(PatientAssignmentDB).where(PatientAssignmentDB.requires_urgent_transport.is_(True))
            )
            return [
                UnassignedPatientInfo(
                    patient_id=str(row.patient_id),
                    treatment_deadline_minutes=row.treatment_deadline_minutes,
                    requires_urgent_transport=row.requires_urgent_transport,
                )
                for row in result.scalars().all()
            ]

    @agent.tool
    async def get_ambulance_utilization(ctx: RunContext[AgentDeps]) -> AmbulanceStatusInfo:
        """Get ambulance fleet utilization statistics."""
        async with ctx.deps.session_factory() as session:
            total = await session.scalar(select(func.count()).select_from(AmbulanceDB)) or 0
            deployed = (
                await session.scalar(
                    select(func.count()).select_from(AmbulanceDB).where(AmbulanceDB.assigned_patient_id.is_not(None))
                )
                or 0
            )
        return AmbulanceStatusInfo(
            total=total,
            deployed=deployed,
            idle=total - deployed,
            utilization_pct=round((deployed / total) * 100, 1) if total > 0 else 0.0,
        )

    return agent


def create_chat_agent(config: AgentConfig) -> Agent[None, str]:
    """Create the Q&A chat agent that answers questions about the current screen context."""
    return Agent(
        model=_make_model(config),
        system_prompt=config.system_prompt,
    )
