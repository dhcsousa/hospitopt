"""API pydantic data models."""

from pydantic import BaseModel
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
