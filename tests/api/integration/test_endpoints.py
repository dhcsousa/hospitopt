"""Integration tests for API endpoints."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from hospitopt_core.db.models import (
    AmbulanceDB,
    HospitalDB,
    PatientAssignmentDB,
    PatientDB,
)


@pytest.mark.asyncio
async def test_health_endpoint(async_client: AsyncClient):
    """Test health endpoint returns healthy status."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["checks"]["api"] == "healthy"
    assert data["checks"]["database"] == "healthy"


@pytest.mark.asyncio
async def test_liveness_endpoint(async_client: AsyncClient):
    """Test liveness endpoint always returns alive."""
    response = await async_client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


@pytest.mark.asyncio
async def test_root_endpoint_browser(async_client: AsyncClient):
    """Test root endpoint redirects browsers to /docs."""
    # Override headers to simulate browser
    async_client.headers.update({"user-agent": "Mozilla/5.0"})
    response = await async_client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


@pytest.mark.asyncio
async def test_root_endpoint_api_client(async_client: AsyncClient):
    """Test root endpoint returns JSON for API clients."""
    # Override headers to simulate API client
    async_client.headers.update({"user-agent": "python-httpx"})
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "HospitOPT API" in data["message"]


@pytest.mark.asyncio
async def test_get_hospitals_unauthorized(unauthorized_client: AsyncClient):
    """Test hospitals endpoint requires authentication."""
    response = await unauthorized_client.get("/hospitals")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_hospitals_empty(async_client: AsyncClient):
    """Test hospitals endpoint returns empty list when no data."""
    response = await async_client.get("/hospitals")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["limit"] == 1000
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_get_hospitals_with_data(async_client: AsyncClient, async_session: AsyncSession):
    """Test hospitals endpoint returns paginated data."""
    # Create test hospitals
    hospitals = [
        HospitalDB(
            id=uuid4(),
            name=f"Hospital {i}",
            bed_capacity=100,
            used_beds=50,
            lat=40.0 + i,
            lon=-74.0 + i,
        )
        for i in range(5)
    ]
    async_session.add_all(hospitals)
    await async_session.commit()

    # Test default pagination
    response = await async_client.get("/hospitals")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 5
    assert data["total"] == 5

    # Test limit and offset
    response = await async_client.get("/hospitals?limit=2&offset=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["limit"] == 2
    assert data["offset"] == 1


@pytest.mark.asyncio
async def test_get_patients_unauthorized(unauthorized_client: AsyncClient):
    """Test patients endpoint requires authentication."""
    response = await unauthorized_client.get("/patients")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_patients_with_data(async_client: AsyncClient, async_session: AsyncSession):
    """Test patients endpoint returns paginated data."""
    # Create test patients
    patients = [
        PatientDB(
            id=uuid4(),
            lat=40.0 + i,
            lon=-74.0 + i,
            time_to_hospital_minutes=30,
            registered_at=datetime.now(UTC),
        )
        for i in range(3)
    ]
    async_session.add_all(patients)
    await async_session.commit()

    response = await async_client.get("/patients")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_get_ambulances_unauthorized(unauthorized_client: AsyncClient):
    """Test ambulances endpoint requires authentication."""
    response = await unauthorized_client.get("/ambulances")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_ambulances_with_data(async_client: AsyncClient, async_session: AsyncSession):
    """Test ambulances endpoint returns paginated data."""
    # Create test ambulances
    ambulances = [
        AmbulanceDB(
            id=uuid4(),
            lat=40.0 + i,
            lon=-74.0 + i,
            assigned_patient_id=None,
        )
        for i in range(4)
    ]
    async_session.add_all(ambulances)
    await async_session.commit()

    response = await async_client.get("/ambulances")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 4
    assert data["total"] == 4


@pytest.mark.asyncio
async def test_get_assignments_unauthorized(unauthorized_client: AsyncClient):
    """Test assignments endpoint requires authentication."""
    response = await unauthorized_client.get("/assignments")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_assignments_with_data(async_client: AsyncClient, async_session: AsyncSession):
    """Test assignments endpoint returns paginated data ordered by optimized_at."""
    # Create test data
    patient_id = uuid4()
    hospital_id = uuid4()
    ambulance_id = uuid4()

    # Create multiple assignments with different timestamps
    assignments = [
        PatientAssignmentDB(
            id=uuid4(),
            patient_id=patient_id,
            hospital_id=hospital_id,
            ambulance_id=ambulance_id,
            estimated_travel_minutes=15 + i,
            deadline_slack_minutes=10,
            treatment_deadline_minutes=30,
            patient_registered_at=datetime.now(UTC),
            requires_urgent_transport=False,
            optimized_at=datetime.now(UTC),
        )
        for i in range(3)
    ]
    async_session.add_all(assignments)
    await async_session.commit()

    response = await async_client.get("/assignments")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    assert data["total"] == 3
    assert data["limit"] == 500  # Default limit for assignments

    # Verify ordering by optimized_at desc
    timestamps = [item["optimized_at"] for item in data["items"]]
    assert timestamps == sorted(timestamps, reverse=True)


@pytest.mark.asyncio
async def test_pagination_validation(async_client: AsyncClient):
    """Test pagination parameter validation."""
    # Test invalid limit (too high)
    response = await async_client.get("/hospitals?limit=6000")
    assert response.status_code == 422

    # Test invalid offset (negative)
    response = await async_client.get("/hospitals?offset=-1")
    assert response.status_code == 422

    # Test invalid limit (zero)
    response = await async_client.get("/hospitals?limit=0")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_api_key_validation(async_client: AsyncClient):
    """Test API key validation with invalid key."""
    # Override authorization header with invalid key
    async_client.headers.update({"Authorization": "Bearer wrong-key"})
    response = await async_client.get("/hospitals")
    assert response.status_code == 401
    assert "Invalid API key" in response.json()["detail"]


@pytest.mark.asyncio
async def test_assignments_pagination(async_client: AsyncClient, async_session: AsyncSession):
    """Test assignments pagination with custom limit."""
    # Create more assignments than the default limit
    patient_id = uuid4()
    hospital_id = uuid4()
    ambulance_id = uuid4()

    assignments = [
        PatientAssignmentDB(
            id=uuid4(),
            patient_id=patient_id,
            hospital_id=hospital_id,
            ambulance_id=ambulance_id,
            estimated_travel_minutes=15,
            deadline_slack_minutes=10,
            treatment_deadline_minutes=30,
            patient_registered_at=datetime.now(UTC),
            requires_urgent_transport=i % 2 == 0,
            optimized_at=datetime.now(UTC),
        )
        for i in range(10)
    ]
    async_session.add_all(assignments)
    await async_session.commit()

    # Test with custom limit
    response = await async_client.get("/assignments?limit=5&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 5
    assert data["total"] >= 10
