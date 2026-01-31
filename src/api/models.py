"""API pydantic data models."""

from pydantic import BaseModel
from core.domain.models import Ambulance, Hospital, Patient, PatientAssignment


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
