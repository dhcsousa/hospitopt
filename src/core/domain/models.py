"""Data models for the hospitopt domain."""

from typing import Annotated, NewType
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, NonNegativeInt, PositiveInt, model_validator

Latitude = Annotated[float, Field(ge=-90.0, le=90.0)]
Longitude = Annotated[float, Field(ge=-180.0, le=180.0)]


class Hospital(BaseModel):
    """Hospital with capacity and location."""

    id: UUID = Field(default_factory=uuid4)
    name: str | None = None
    bed_capacity: NonNegativeInt
    used_beds: NonNegativeInt = 0
    lat: Latitude
    lon: Longitude

    @model_validator(mode="after")
    def validate_beds(self) -> "Hospital":
        """Ensure used beds do not exceed capacity."""
        if self.used_beds > self.bed_capacity:
            raise ValueError(f"used_beds ({self.used_beds}) cannot exceed bed_capacity ({self.bed_capacity})")
        return self


class Patient(BaseModel):
    """Patient with location and urgency constraint."""

    id: UUID = Field(default_factory=uuid4)
    lat: Latitude
    lon: Longitude
    time_to_hospital_minutes: PositiveInt
    registered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Ambulance(BaseModel):
    """Ambulance with location and optional assigned patient."""

    id: UUID = Field(default_factory=uuid4)
    lat: Latitude
    lon: Longitude
    assigned_patient_id: UUID | None = None


class RouteMatrixEntry(BaseModel):
    """Single route matrix element with duration in minutes."""

    origin_index: int
    destination_index: int
    duration_minutes: PositiveInt


PatientIndex = NewType("PatientIndex", int)
HospitalIndex = NewType("HospitalIndex", int)
AmbulanceIndex = NewType("AmbulanceIndex", int)


class MinutesTables(BaseModel):
    """Travel-time tables for optimization."""

    ambulance_to_patient: dict[tuple["AmbulanceIndex", "PatientIndex"], PositiveInt]
    patient_to_hospital: dict[tuple["PatientIndex", "HospitalIndex"], PositiveInt]


class PatientAssignment(BaseModel):
    """Optimization assignment for a single patient."""

    patient_id: UUID
    hospital_id: UUID | None = None
    ambulance_id: UUID | None = None
    estimated_travel_minutes: PositiveInt | None = None
    deadline_slack_minutes: int | None = None
    treatment_deadline_minutes: PositiveInt
    patient_registered_at: datetime
    requires_urgent_transport: bool = False
    optimized_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OptimizationResult(BaseModel):
    """Optimization output with assignments and summary metrics."""

    assignments: list[PatientAssignment]
    unassigned_patient_ids: list[UUID]
    max_lives_saved: NonNegativeInt = 0
    capacity_shortfall: NonNegativeInt = 0
    ambulance_shortfall: NonNegativeInt = 0
