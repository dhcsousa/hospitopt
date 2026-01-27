"""SQLAlchemy ORM models for hospitopt."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base declarative class for ORM models."""


class HospitalDB(Base):
    """Hospital ORM model."""

    __tablename__ = "hospitals"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    bed_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    used_beds: Mapped[int] = mapped_column(Integer, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)


class PatientDB(Base):
    """Patient ORM model."""

    __tablename__ = "patients"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    time_to_hospital_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class AmbulanceDB(Base):
    """Ambulance ORM model."""

    __tablename__ = "ambulances"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    assigned_patient_id: Mapped[UUID | None] = mapped_column(Uuid(), nullable=True)


class PatientAssignmentDB(Base):
    """Patient assignment ORM model."""

    __tablename__ = "patient_assignments"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(Uuid(), nullable=False)
    hospital_id: Mapped[UUID | None] = mapped_column(Uuid(), nullable=True)
    ambulance_id: Mapped[UUID | None] = mapped_column(Uuid(), nullable=True)
    estimated_travel_minutes: Mapped[int | None] = mapped_column("travel_time_minutes", Integer, nullable=True)
    deadline_slack_minutes: Mapped[int | None] = mapped_column("time_left_minutes", Integer, nullable=True)
    treatment_deadline_minutes: Mapped[int] = mapped_column("time_to_hospital_minutes", Integer, nullable=False)
    patient_registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requires_urgent_transport: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    optimized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
