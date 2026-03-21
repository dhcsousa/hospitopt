"""API pydantic data models."""

from pydantic import BaseModel, Field
from hospitopt_core.domain.models import Ambulance, Hospital, Patient, PatientAssignment


class HospitalsPage(BaseModel):
    items: list[Hospital]
    total: int
    limit: int
    offset: int


class PatientsPage(BaseModel):
    items: list[Patient]
    total: int
    limit: int
    offset: int


class AmbulancesPage(BaseModel):
    items: list[Ambulance]
    total: int
    limit: int
    offset: int


class AssignmentsPage(BaseModel):
    items: list[PatientAssignment]
    total: int
    limit: int
    offset: int


class SituationSummary(BaseModel):
    """Structured summary of the current MCE situation."""

    total_patients: int
    assigned_patients: int
    unassigned_patients: int
    urgent_patients: int
    total_hospitals: int
    total_beds: int
    used_beds: int
    available_beds: int
    total_ambulances: int
    deployed_ambulances: int
    idle_ambulances: int


class HospitalCapacityInfo(BaseModel):
    name: str | None
    bed_capacity: int
    used_beds: int
    available_beds: int
    occupancy_pct: float


class CriticalPatientInfo(BaseModel):
    patient_id: str
    deadline_slack_minutes: int | None
    treatment_deadline_minutes: int
    hospital_id: str | None
    ambulance_id: str | None
    requires_urgent_transport: bool


class UnassignedPatientInfo(BaseModel):
    patient_id: str
    treatment_deadline_minutes: int
    requires_urgent_transport: bool


class AmbulanceStatusInfo(BaseModel):
    total: int
    deployed: int
    idle: int
    utilization_pct: float


class SitrepReport(BaseModel):
    """Structured situation report returned by the SITREP agent."""

    patient_overview: str = Field(
        description="Markdown summary of patient counts: total, assigned, unassigned, and urgent."
    )
    hospital_capacity: str = Field(
        description="Markdown summary of hospital bed capacity, occupancy, and which hospitals are near full."
    )
    ambulance_fleet_status: str = Field(
        description="Markdown summary of ambulance deployment: total, deployed, idle, utilization."
    )
    critical_patients: str = Field(
        description="Markdown section listing patients with deadline slack <= 5 minutes. "
        "Include patient ID, slack, deadline, and assignment status."
    )
    unassigned_patients: str = Field(
        description="Markdown section listing patients that require urgent transport "
        "(no timely hospital/ambulance assignment). Include patient ID and deadline."
    )
    action_required: str = Field(
        description="Actionable recommendations for the emergency coordinator based on the data."
    )
    summary: str = Field(description="A concise 2-3 sentence overall situation summary.")
