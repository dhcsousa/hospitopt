from hospitopt_core.domain.models import Ambulance, Hospital, MinutesTables, Patient
from hospitopt_worker import optimize


def test_optimize_assigns_feasible():
    minutes_tables = MinutesTables(
        patient_to_hospital={(0, 0): 5},
        ambulance_to_patient={(0, 0): 5},
    )

    hospitals = [Hospital(name="H", bed_capacity=1, used_beds=0, lat=0.0, lon=0.0)]
    patients = [Patient(lat=1.0, lon=1.0, time_to_hospital_minutes=20)]
    ambulances = [Ambulance(lat=2.0, lon=2.0)]

    result = optimize.optimize_allocation(
        minutes_tables=minutes_tables,
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


def test_optimize_skips_over_capacity():
    minutes_tables = MinutesTables(
        patient_to_hospital={(0, 0): 5},
        ambulance_to_patient={(0, 0): 5},
    )

    hospitals = [Hospital(name="H", bed_capacity=1, used_beds=1, lat=0.0, lon=0.0)]
    patients = [Patient(lat=1.0, lon=1.0, time_to_hospital_minutes=20)]
    ambulances = [Ambulance(lat=2.0, lon=2.0)]

    result = optimize.optimize_allocation(
        minutes_tables=minutes_tables,
        hospitals=hospitals,
        patients=patients,
        ambulances=ambulances,
        speed_factor=1.0,
    )

    assert result.max_lives_saved == 0
    assert len(result.assignments) == 1
    assert result.assignments[0].requires_urgent_transport is True


def test_optimize_prioritizes_urgent():
    # two patients, one hospital, one ambulance
    # patient 0: travel 18, time_to_hospital 20 => urgent (1/20 = 0.05)
    # patient 1: travel 12, time_to_hospital 50 => less urgent (1/50 = 0.02)
    minutes_tables = MinutesTables(
        patient_to_hospital={(0, 0): 10, (1, 0): 4},
        ambulance_to_patient={(0, 0): 8, (0, 1): 8},
    )

    hospitals = [Hospital(name="H", bed_capacity=1, used_beds=0, lat=0.0, lon=0.0)]
    patients = [
        Patient(lat=1.0, lon=1.0, time_to_hospital_minutes=20),
        Patient(lat=2.0, lon=2.0, time_to_hospital_minutes=50),
    ]
    ambulances = [Ambulance(lat=3.0, lon=3.0)]

    result = optimize.optimize_allocation(
        minutes_tables=minutes_tables,
        hospitals=hospitals,
        patients=patients,
        ambulances=ambulances,
        speed_factor=1.0,
    )

    assigned = [a for a in result.assignments if not a.requires_urgent_transport]
    assert len(assigned) == 1
    assert assigned[0].patient_id == patients[0].id


def test_optimize_prefers_closer_hospital_for_same_patient() -> None:
    # One patient, one ambulance, two hospitals with equal capacity.
    # Optimizer should choose the nearer hospital (higher slack).
    minutes_tables = MinutesTables(
        patient_to_hospital={(0, 0): 5, (0, 1): 25},
        ambulance_to_patient={(0, 0): 10},
    )

    hospitals = [
        Hospital(name="Near", bed_capacity=1, used_beds=0, lat=0.0, lon=0.0),
        Hospital(name="Far", bed_capacity=1, used_beds=0, lat=1.0, lon=1.0),
    ]
    patients = [Patient(lat=1.0, lon=1.0, time_to_hospital_minutes=60)]
    ambulances = [Ambulance(lat=2.0, lon=2.0)]

    result = optimize.optimize_allocation(
        minutes_tables=minutes_tables,
        hospitals=hospitals,
        patients=patients,
        ambulances=ambulances,
        speed_factor=1.0,
    )

    assigned = [a for a in result.assignments if not a.requires_urgent_transport]
    assert len(assigned) == 1
    assert assigned[0].hospital_id == hospitals[0].id


def test_optimize_handles_empty_patient_list() -> None:
    minutes_tables = MinutesTables(patient_to_hospital={}, ambulance_to_patient={})

    hospitals = [Hospital(name="H", bed_capacity=1, used_beds=0, lat=0.0, lon=0.0)]
    ambulances = [Ambulance(lat=2.0, lon=2.0)]

    result = optimize.optimize_allocation(
        minutes_tables=minutes_tables,
        hospitals=hospitals,
        patients=[],
        ambulances=ambulances,
        speed_factor=1.0,
    )

    assert result.assignments == []
    assert result.unassigned_patient_ids == []
    assert result.max_lives_saved == 0


def test_optimize_flags_patient_impossible_within_deadline() -> None:
    minutes_tables = MinutesTables(
        patient_to_hospital={(0, 0): 20},
        ambulance_to_patient={(0, 0): 15},
    )

    hospitals = [Hospital(name="H", bed_capacity=1, used_beds=0, lat=0.0, lon=0.0)]
    patients = [Patient(lat=1.0, lon=1.0, time_to_hospital_minutes=30)]
    ambulances = [Ambulance(lat=2.0, lon=2.0)]

    result = optimize.optimize_allocation(
        minutes_tables=minutes_tables,
        hospitals=hospitals,
        patients=patients,
        ambulances=ambulances,
        speed_factor=1.0,
    )

    assert len(result.assignments) == 1
    assignment = result.assignments[0]
    assert assignment.requires_urgent_transport is True
    assert assignment.estimated_travel_minutes == 35
    assert assignment.deadline_slack_minutes == -5
