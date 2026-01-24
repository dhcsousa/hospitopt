from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, NonNegativeInt, PositiveInt, model_validator

Latitude = Annotated[float, Field(ge=-90.0, le=90.0)]
Longitude = Annotated[float, Field(ge=-180.0, le=180.0)]


class Hospital(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str | None = None
    bed_capacity: NonNegativeInt
    used_beds: NonNegativeInt = 0
    lat: Latitude
    lon: Longitude

    @model_validator(mode="after")
    def validate_beds(self) -> "Hospital":
        if self.used_beds > self.bed_capacity:
            raise ValueError(f"used_beds ({self.used_beds}) cannot exceed bed_capacity ({self.bed_capacity})")
        return self


class Patient(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    lat: Latitude
    lon: Longitude
    time_to_hospital_minutes: PositiveInt


class Ambulance(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    lat: Latitude
    lon: Longitude
    assigned_patient_id: UUID | None = None
