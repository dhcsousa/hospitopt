import pytest

from core.models import Ambulance, Hospital, MinutesTables, Patient
from worker import optimize


@pytest.mark.asyncio
async def test_optimize_assigns_feasible(monkeypatch):
    async def fake_build_minutes_tables(client, patients, hospitals, ambulances, travel_mode=None):
        # patient->hospital and ambulance->patient matrices
        return MinutesTables(
            patient_to_hospital={(0, 0): 5},
            ambulance_to_patient={(0, 0): 5},
        )

    monkeypatch.setattr(optimize, "build_minutes_tables", fake_build_minutes_tables)

    hospitals = [Hospital(name="H", bed_capacity=1, used_beds=0, lat=0.0, lon=0.0)]
    patients = [Patient(lat=1.0, lon=1.0, time_to_hospital_minutes=20)]
    ambulances = [Ambulance(lat=2.0, lon=2.0)]

    result = await optimize.optimize_allocation(
        routes_client=None,
        hospitals=hospitals,
        patients=patients,
        ambulances=ambulances,
        speed_factor=1.0,
    )

    assert result.max_lives_saved == 1
    assigned = [a for a in result.assignments if not a.requires_urgent_transport]
    assert len(assigned) == 1
    assert assigned[0].patient_id == patients[0].id
    assert assigned[0].hospital_id == hospitals[0].id


@pytest.mark.asyncio
async def test_optimize_skips_over_capacity(monkeypatch):
    async def fake_build_minutes_tables(client, patients, hospitals, ambulances, travel_mode=None):
        return optimize.MinutesTables(
            patient_to_hospital={(0, 0): 5},
            ambulance_to_patient={(0, 0): 5},
        )

    monkeypatch.setattr(optimize, "build_minutes_tables", fake_build_minutes_tables)

    hospitals = [Hospital(name="H", bed_capacity=1, used_beds=1, lat=0.0, lon=0.0)]
    patients = [Patient(lat=1.0, lon=1.0, time_to_hospital_minutes=20)]
    ambulances = [Ambulance(lat=2.0, lon=2.0)]

    result = await optimize.optimize_allocation(
        routes_client=None,
        hospitals=hospitals,
        patients=patients,
        ambulances=ambulances,
        speed_factor=1.0,
    )

    assert result.max_lives_saved == 0
    assert len(result.assignments) == 1
    assert result.assignments[0].requires_urgent_transport is True


@pytest.mark.asyncio
async def test_optimize_prioritizes_urgent(monkeypatch):
    async def fake_build_minutes_tables(client, patients, hospitals, ambulances, travel_mode=None):
        # two patients, one hospital, one ambulance
        # patient 0: travel 18, time_to_hospital 20 => slack 2 (weight 0.5)
        # patient 1: travel 12, time_to_hospital 50 => slack 38 (weight ~0.026)
        p_to_h = {(0, 0): 10, (1, 0): 4}
        a_to_p = {(0, 0): 8, (0, 1): 8}
        return optimize.MinutesTables(
            patient_to_hospital=p_to_h,
            ambulance_to_patient=a_to_p,
        )

    monkeypatch.setattr(optimize, "build_minutes_tables", fake_build_minutes_tables)

    hospitals = [Hospital(name="H", bed_capacity=1, used_beds=0, lat=0.0, lon=0.0)]
    patients = [
        Patient(lat=1.0, lon=1.0, time_to_hospital_minutes=20),
        Patient(lat=2.0, lon=2.0, time_to_hospital_minutes=50),
    ]
    ambulances = [Ambulance(lat=3.0, lon=3.0)]

    result = await optimize.optimize_allocation(
        routes_client=None,
        hospitals=hospitals,
        patients=patients,
        ambulances=ambulances,
        speed_factor=1.0,
    )

    assigned = [a for a in result.assignments if not a.requires_urgent_transport]
    assert len(assigned) == 1
    assert assigned[0].patient_id == patients[0].id
