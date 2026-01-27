"""Optimization logic for assigning patients to hospitals and ambulances."""

from typing import Iterable
from uuid import UUID

import pyomo.environ as pyo
from google.maps import routing_v2
from pydantic import PositiveFloat

from core.domain.models import (
    Ambulance,
    AmbulanceIndex,
    Hospital,
    HospitalIndex,
    MinutesTables,
    OptimizationResult,
    Patient,
    PatientAssignment,
    PatientIndex,
)
from worker.routes import build_minutes_tables


async def optimize_allocation(
    routes_client: routing_v2.RoutesAsyncClient,
    hospitals: Iterable[Hospital],
    patients: Iterable[Patient],
    ambulances: Iterable[Ambulance],
    travel_mode: routing_v2.RouteTravelMode = routing_v2.RouteTravelMode.DRIVE,
    speed_factor: PositiveFloat = 1.3,  # to account for priority vehicle speedups, 30% faster by default
) -> OptimizationResult:
    """Optimize patient allocations with urgency-weighted objective.

    Args:
        routes_client: Google Routes async client used for travel-time matrices.
        hospitals: Available hospitals with capacities.
        patients: Patients to allocate with urgency constraints.
        ambulances: Available ambulances for transport.
        travel_mode: Google Routes travel mode. Defaults to DRIVE.
        speed_factor: Multiplier to reduce travel time for priority transport. Defaults to 1.3.

    Returns:
        OptimizationResult containing assignments and summary metrics.
    """
    hospital_list = list(hospitals)
    patient_list = list(patients)
    ambulance_list = list(ambulances)

    total_capacity = sum(hospital.bed_capacity - hospital.used_beds for hospital in hospital_list)
    capacity_shortfall = max(0, len(patient_list) - total_capacity)
    ambulance_shortfall = max(0, len(patient_list) - len(ambulance_list))

    feasible: dict[tuple[PatientIndex, AmbulanceIndex, HospitalIndex], int] = {}
    feasible_weights: dict[tuple[PatientIndex, AmbulanceIndex, HospitalIndex], float] = {}
    minutes_tables: MinutesTables = await build_minutes_tables(
        routes_client, patient_list, hospital_list, ambulance_list, travel_mode=travel_mode
    )
    a_p_minutes = minutes_tables.ambulance_to_patient
    p_h_minutes = minutes_tables.patient_to_hospital
    for p_index, patient in enumerate(patient_list):
        for h_index, hospital in enumerate(hospital_list):
            if hospital.bed_capacity <= hospital.used_beds:  # hospital already over maximum capacity
                continue
            for a_index, ambulance in enumerate(ambulance_list):
                ap = a_p_minutes.get((AmbulanceIndex(a_index), PatientIndex(p_index)))
                ph = p_h_minutes.get((PatientIndex(p_index), HospitalIndex(h_index)))
                if ap is None or ph is None:
                    continue
                raw_travel_minutes = ap + ph
                travel_minutes = round(raw_travel_minutes / speed_factor)
                if travel_minutes <= patient.time_to_hospital_minutes:
                    slack = patient.time_to_hospital_minutes - travel_minutes
                    if slack <= 0:
                        continue
                    feasible[(PatientIndex(p_index), AmbulanceIndex(a_index), HospitalIndex(h_index))] = travel_minutes
                    feasible_weights[(PatientIndex(p_index), AmbulanceIndex(a_index), HospitalIndex(h_index))] = (
                        1.0 / slack
                    )

    if not feasible:
        # prevent solver from failing on empty model
        urgent_assignments = [
            PatientAssignment(
                patient_id=patient.id,
                deadline_slack_minutes=patient.time_to_hospital_minutes,
                treatment_deadline_minutes=patient.time_to_hospital_minutes,
                patient_registered_at=patient.registered_at,
                requires_urgent_transport=True,
            )
            for patient in patient_list
        ]
        return OptimizationResult(
            assignments=urgent_assignments,
            unassigned_patient_ids=[patient.id for patient in patient_list],
            max_lives_saved=0,
            capacity_shortfall=capacity_shortfall,
            ambulance_shortfall=ambulance_shortfall,
        )

    model = pyo.ConcreteModel()
    model.F = pyo.Set(initialize=list(feasible.keys()), dimen=3)
    model.P = pyo.RangeSet(0, len(patient_list) - 1)
    model.A = pyo.RangeSet(0, len(ambulance_list) - 1)
    model.H = pyo.RangeSet(0, len(hospital_list) - 1)

    model.assign = pyo.Var(model.F, within=pyo.Binary)

    def patient_limit(m: pyo.ConcreteModel, p_index: int) -> pyo.Constraint:
        """Each patient can be assigned at most once."""
        if not any(key[0] == p_index for key in m.F):
            return pyo.Constraint.Feasible  # When no feasible assignments exist for this patient
        return sum(m.assign[key] for key in m.F if key[0] == p_index) <= 1

    model.patient_limit = pyo.Constraint(model.P, rule=patient_limit)

    def hospital_capacity(m: pyo.ConcreteModel, h_index: int) -> pyo.Constraint:
        """Hospital capacity cannot be exceeded."""
        available = max(0, hospital_list[h_index].bed_capacity - hospital_list[h_index].used_beds)
        if not any(key[2] == h_index for key in m.F):
            return pyo.Constraint.Feasible  # When no feasible assignments exist for this hospital
        return sum(m.assign[key] for key in m.F if key[2] == h_index) <= available

    model.hospital_capacity = pyo.Constraint(model.H, rule=hospital_capacity)

    def ambulance_limit(m: pyo.ConcreteModel, a_index: int) -> pyo.Constraint:
        """Each ambulance can be assigned at most once."""
        if not any(key[1] == a_index for key in m.F):
            return pyo.Constraint.Feasible  # When no feasible assignments exist for this ambulance
        return sum(m.assign[key] for key in m.F if key[1] == a_index) <= 1

    model.ambulance_limit = pyo.Constraint(model.A, rule=ambulance_limit)

    model.objective = pyo.Objective(
        expr=sum(model.assign[key] * feasible_weights[key] for key in model.F),
        sense=pyo.maximize,
    )  # prioritizes patients with less time to spare

    solver = pyo.SolverFactory("glpk")
    if solver is None or not solver.available():
        raise RuntimeError("No compatible Pyomo solver available. Install GLPK or set up another MILP solver.")
    solver.solve(model, tee=False)

    assignments: list[PatientAssignment] = []
    assigned_patients: set[UUID] = set()
    for key in feasible:
        if pyo.value(model.assign[key]) != 1:
            continue
        p_index, a_index, h_index = key
        patient = patient_list[p_index]
        hospital = hospital_list[h_index]
        ambulance = ambulance_list[a_index]
        assignments.append(
            PatientAssignment(
                patient_id=patient.id,
                hospital_id=hospital.id,
                ambulance_id=ambulance.id if ambulance else None,
                estimated_travel_minutes=feasible[key],
                deadline_slack_minutes=patient.time_to_hospital_minutes - feasible[key],
                treatment_deadline_minutes=patient.time_to_hospital_minutes,
                patient_registered_at=patient.registered_at,
                requires_urgent_transport=False,
            )
        )
        assigned_patients.add(patient.id)

    unassigned = [patient.id for patient in patient_list if patient.id not in assigned_patients]
    if unassigned:
        assignments.extend(
            PatientAssignment(
                patient_id=patient_id,
                deadline_slack_minutes=next(
                    patient.time_to_hospital_minutes for patient in patient_list if patient.id == patient_id
                ),
                treatment_deadline_minutes=next(
                    patient.time_to_hospital_minutes for patient in patient_list if patient.id == patient_id
                ),
                patient_registered_at=next(
                    patient.registered_at for patient in patient_list if patient.id == patient_id
                ),
                requires_urgent_transport=True,
            )
            for patient_id in unassigned
        )

    return OptimizationResult(
        assignments=assignments,
        unassigned_patient_ids=unassigned,
        max_lives_saved=len(assigned_patients),
        capacity_shortfall=capacity_shortfall,
        ambulance_shortfall=ambulance_shortfall,
    )
