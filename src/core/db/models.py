"""SQLAlchemy ORM models for hospitopt."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base declarative class for ORM models."""


class HospitalDB(Base):
    """Hospital ORM model."""

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    bed_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    used_beds: Mapped[int] = mapped_column(Integer, nullable=False)
    lat: Mapped[float] = mapped_column(float, nullable=False)
    lon: Mapped[float] = mapped_column(float, nullable=False)


class PatientDB(Base):
    """Patient ORM model."""

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    lat: Mapped[float] = mapped_column(float, nullable=False)
    lon: Mapped[float] = mapped_column(float, nullable=False)
    time_to_hospital_minutes: Mapped[int] = mapped_column(Integer, nullable=False)


class AmbulanceDB(Base):
    """Ambulance ORM model."""

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    lat: Mapped[float] = mapped_column(float, nullable=False)
    lon: Mapped[float] = mapped_column(float, nullable=False)
    assigned_patient_id: Mapped[UUID | None] = mapped_column(Uuid(), nullable=True)


class PatientAssignmentDB(Base):
    """Patient assignment ORM model."""

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(Uuid(), nullable=False)
    hospital_id: Mapped[UUID | None] = mapped_column(Uuid(), nullable=True)
    ambulance_id: Mapped[UUID | None] = mapped_column(Uuid(), nullable=True)
    travel_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requires_urgent_transport: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    optimized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
