import asyncio
import hashlib
import os
from typing import Any

import distinctipy
import httpx
import reflex as rx

API_BASE_URL = os.getenv("HOSPITOPT_API_URL")
API_KEY = os.getenv("HOSPITOPT_API_KEY")

if API_BASE_URL is None:
    raise RuntimeError("HOSPITOPT_API_URL environment variable is not set")
else:
    API_BASE_URL = API_BASE_URL.rstrip("/")

if API_KEY is None:
    raise RuntimeError("HOSPITOPT_API_KEY environment variable is not set")


class DashboardState(rx.State):
    assignments: list[dict[str, Any]] = []
    patients: list[dict[str, Any]] = []
    hospitals: list[dict[str, Any]] = []
    ambulances: list[dict[str, Any]] = []
    map_center_lat: float = 38.7223
    map_center_lon: float = -9.1393
    map_zoom: float = 12.0
    selected_tab: str = "map"
    is_loading: bool = False
    error_message: str = ""
    api_status: str = "checking"  # "online", "offline", "checking"
    data_fingerprint: str = ""

    async def load_data(self) -> None:
        self.is_loading = True
        self.error_message = ""
        try:
            headers = {"Authorization": f"Bearer {API_KEY}"}
            async with httpx.AsyncClient(headers=headers) as client:
                hospitals_req = client.get(f"{API_BASE_URL}/hospitals", params={"limit": 1000, "offset": 0})
                patients_req = client.get(f"{API_BASE_URL}/patients", params={"limit": 1000, "offset": 0})
                ambulances_req = client.get(f"{API_BASE_URL}/ambulances", params={"limit": 1000, "offset": 0})
                assignments_req = client.get(f"{API_BASE_URL}/assignments", params={"limit": 500, "offset": 0})
                hospitals_resp, patients_resp, ambulances_resp, assignments_resp = await asyncio.gather(
                    hospitals_req,
                    patients_req,
                    ambulances_req,
                    assignments_req,
                )
                hospitals_resp.raise_for_status()
                patients_resp.raise_for_status()
                ambulances_resp.raise_for_status()
                assignments_resp.raise_for_status()
                hospitals_data = hospitals_resp.json()
                patients_data = patients_resp.json()
                ambulances_data = ambulances_resp.json()
                assignments_data = assignments_resp.json()
        except httpx.HTTPError as exc:
            self.error_message = f"Failed to load data: {exc}"
            self.is_loading = False
            return

        self.assignments = assignments_data.get("items", [])
        self.patients = patients_data.get("items", [])
        self.hospitals = hospitals_data.get("items", [])
        self.ambulances = ambulances_data.get("items", [])

        if self.patients:
            lat_sum = sum(patient["lat"] for patient in self.patients)
            lon_sum = sum(patient["lon"] for patient in self.patients)
            count = len(self.patients)
            self.map_center_lat = lat_sum / count
            self.map_center_lon = lon_sum / count

        # Compute a fingerprint so the SITREP agent knows when data changed.
        fp_parts = [
            str(len(self.patients)),
            str(len(self.hospitals)),
            str(len(self.ambulances)),
            str(len(self.assignments)),
        ]
        for a in sorted(self.assignments, key=lambda x: str(x.get("id", ""))):
            fp_parts.append(f"{a.get('patient_id')}-{a.get('hospital_id')}-{a.get('ambulance_id')}")
        self.data_fingerprint = hashlib.sha256("|".join(fp_parts).encode()).hexdigest()[:16]

        self.is_loading = False

    @rx.event(background=True)
    async def start_health_check_polling(self) -> None:
        """Background task that polls API health every second."""
        while True:
            # HTTP outside the state lock so it doesn't block other tasks
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    response = await client.get(f"{API_BASE_URL}/health")
                status = "online" if response.status_code == 200 else "offline"
            except httpx.HTTPError:
                status = "offline"
            async with self:
                self.api_status = status
            await asyncio.sleep(1)

    @rx.event(background=True)
    async def start_position_polling(self) -> None:
        """Background task that refreshes ambulance/patient positions every second.

        HTTP is done OUTSIDE async with self so the state lock is held only
        for the brief state-write, not for the full network round-trip.
        """
        while True:
            try:
                headers = {"Authorization": f"Bearer {API_KEY}"}
                async with httpx.AsyncClient(headers=headers) as client:
                    ambulances_resp, patients_resp = await asyncio.gather(
                        client.get(f"{API_BASE_URL}/ambulances", params={"limit": 1000, "offset": 0}),
                        client.get(f"{API_BASE_URL}/patients", params={"limit": 1000, "offset": 0}),
                    )
                    ambulances_resp.raise_for_status()
                    patients_resp.raise_for_status()
                    ambulances = ambulances_resp.json().get("items", [])
                    patients = patients_resp.json().get("items", [])
                async with self:
                    self.ambulances = ambulances
                    self.patients = patients
            except httpx.HTTPError:
                pass  # silent — full load_data will surface errors
            await asyncio.sleep(1)

    @rx.event(background=True)
    async def start_data_polling(self) -> None:
        """Background task that refreshes all data every 5 seconds.

        HTTP is done OUTSIDE async with self so the state lock is held only
        for the brief state-write, not for the full network round-trip.
        """
        while True:
            try:
                headers = {"Authorization": f"Bearer {API_KEY}"}
                async with httpx.AsyncClient(headers=headers) as client:
                    hospitals_resp, patients_resp, ambulances_resp, assignments_resp = await asyncio.gather(
                        client.get(f"{API_BASE_URL}/hospitals", params={"limit": 1000, "offset": 0}),
                        client.get(f"{API_BASE_URL}/patients", params={"limit": 1000, "offset": 0}),
                        client.get(f"{API_BASE_URL}/ambulances", params={"limit": 1000, "offset": 0}),
                        client.get(f"{API_BASE_URL}/assignments", params={"limit": 500, "offset": 0}),
                    )
                    hospitals_resp.raise_for_status()
                    patients_resp.raise_for_status()
                    ambulances_resp.raise_for_status()
                    assignments_resp.raise_for_status()
                    hospitals = hospitals_resp.json().get("items", [])
                    patients = patients_resp.json().get("items", [])
                    ambulances = ambulances_resp.json().get("items", [])
                    assignments = assignments_resp.json().get("items", [])

                fp_parts = [str(len(patients)), str(len(hospitals)), str(len(ambulances)), str(len(assignments))]
                for a in sorted(assignments, key=lambda x: str(x.get("id", ""))):
                    fp_parts.append(f"{a.get('patient_id')}-{a.get('hospital_id')}-{a.get('ambulance_id')}")
                fingerprint = hashlib.sha256("|".join(fp_parts).encode()).hexdigest()[:16]

                async with self:
                    self.hospitals = hospitals
                    self.patients = patients
                    self.ambulances = ambulances
                    self.assignments = assignments
                    self.data_fingerprint = fingerprint
                    self.error_message = ""
            except httpx.HTTPError as exc:
                async with self:
                    self.error_message = f"Failed to load data: {exc}"
            await asyncio.sleep(5)

    def _find_by_id(self, items: list[dict[str, Any]], entity_id: str | None) -> dict[str, Any] | None:
        if not entity_id:
            return None
        for item in items:
            if item.get("id") == entity_id:
                return item
        return None

    def _fly_to(self, lat: float, lon: float) -> None:
        self.map_center_lat = lat
        self.map_center_lon = lon
        self.map_zoom = 15.0

    def select_patient(self, patient_id: str | None) -> None:
        self.selected_tab = "map"
        patient = self._find_by_id(self.patients, patient_id)
        if patient is None:
            return
        self._fly_to(patient["lat"], patient["lon"])

    def select_hospital(self, hospital_id: str | None) -> None:
        self.selected_tab = "map"
        hospital = self._find_by_id(self.hospitals, hospital_id)
        if hospital is None:
            return
        self._fly_to(hospital["lat"], hospital["lon"])

    def select_ambulance(self, ambulance_id: str | None) -> None:
        self.selected_tab = "map"
        ambulance = self._find_by_id(self.ambulances, ambulance_id)
        if ambulance is None:
            return
        self._fly_to(ambulance["lat"], ambulance["lon"])

    def set_tab(self, value: str) -> None:
        self.selected_tab = value

    def _active_patient_ids(self) -> set[str]:
        return {
            patient_id
            for patient in self.patients
            if (patient_id := patient.get("id")) and patient.get("status") in {"waiting", "in_transit"}
        }

    def _current_assignments(self) -> list[dict[str, Any]]:
        """Return newest assignment per active patient.

        /assignments includes historical rows. The API returns newest-first,
        so keep the first row per patient and ignore delivered patients.
        """
        active_patient_ids = self._active_patient_ids()
        assignments_by_patient: dict[str, dict[str, Any]] = {}
        for assignment in self.assignments:
            patient_id = assignment.get("patient_id")
            if not patient_id or patient_id not in active_patient_ids:
                continue
            if patient_id not in assignments_by_patient:
                assignments_by_patient[patient_id] = assignment
        return list(assignments_by_patient.values())

    @staticmethod
    def _compute_badge_type(assignment: dict[str, Any]) -> str:
        if not assignment.get("requires_urgent_transport"):
            return "assigned"
        slack = assignment.get("deadline_slack_minutes")
        if slack is not None and slack <= 0:
            return "impossible"
        return "unassigned"

    @rx.var(cache=True)
    def priority_assignments(self) -> list[dict[str, Any]]:
        def sort_key(assignment: dict[str, Any]) -> int:
            deadline = assignment.get("treatment_deadline_minutes")
            return deadline if deadline is not None else 10**9

        urgent_only = [
            {**assignment, "badge_type": self._compute_badge_type(assignment)}
            for assignment in self._current_assignments()
            if assignment.get("requires_urgent_transport")
        ]
        return sorted(urgent_only, key=sort_key)[:10]

    @rx.var(cache=True)
    def sorted_assignments_by_slack(self) -> list[dict[str, Any]]:
        def sort_key(assignment: dict[str, Any]) -> tuple[int, int, int]:
            slack = assignment.get("deadline_slack_minutes")
            deadline = assignment.get("treatment_deadline_minutes")
            slack_missing = 1 if slack is None else 0
            slack_value = slack if slack is not None else 10**9
            deadline_value = deadline if deadline is not None else 10**9
            return (slack_missing, slack_value, deadline_value)

        return sorted(
            ({**a, "badge_type": self._compute_badge_type(a)} for a in self._current_assignments()),
            key=sort_key,
        )

    @rx.var(cache=True)
    def allocated_ambulance_pct(self) -> str:
        total = len(self.ambulances)
        if total == 0:
            return "0%"
        allocated_ambulance_ids = {
            assignment.get("ambulance_id")
            for assignment in self._current_assignments()
            if assignment.get("ambulance_id")
        }
        busy = len(allocated_ambulance_ids)
        return f"{(busy / total) * 100:.1f}%"

    @rx.var(cache=True)
    def patients_without_timely_response(self) -> int:
        if not self.patients:
            return 0

        assignments_by_patient = {a.get("patient_id"): a for a in self._current_assignments() if a.get("patient_id")}
        without_timely = 0
        for patient in self.patients:
            if patient.get("status") == "delivered":
                continue
            assignment = assignments_by_patient.get(patient.get("id"))
            if assignment is None:
                without_timely += 1
                continue
            slack = assignment.get("deadline_slack_minutes")
            if assignment.get("ambulance_id") is None or (slack is not None and slack < 0):
                without_timely += 1
        return without_timely

    @rx.var(cache=True)
    def patients_in_danger_alert_level(self) -> str:
        count = self.patients_without_timely_response
        if count >= 10:
            return "critical"
        if count >= 5:
            return "warning"
        return "normal"

    @rx.var(cache=True)
    def occupied_beds_pct(self) -> str:
        total_beds = sum(hospital.get("bed_capacity") or 0 for hospital in self.hospitals)
        if total_beds == 0:
            return "0%"
        used_beds = sum(hospital.get("used_beds") or 0 for hospital in self.hospitals)
        return f"{(used_beds / total_beds) * 100:.1f}%"

    @rx.var(cache=True)
    def allocated_ambulance_alert_level(self) -> str:
        total = len(self.ambulances)
        if total == 0:
            return "normal"
        allocated_ambulance_ids = {
            assignment.get("ambulance_id")
            for assignment in self._current_assignments()
            if assignment.get("ambulance_id")
        }
        ratio = len(allocated_ambulance_ids) / total
        if ratio >= 0.9:
            return "critical"
        if ratio >= 0.8:
            return "warning"
        return "normal"

    @rx.var(cache=True)
    def occupied_beds_alert_level(self) -> str:
        total_beds = sum(hospital.get("bed_capacity") or 0 for hospital in self.hospitals)
        if total_beds == 0:
            return "normal"
        used_beds = sum(hospital.get("used_beds") or 0 for hospital in self.hospitals)
        ratio = used_beds / total_beds
        if ratio >= 0.9:
            return "critical"
        if ratio >= 0.8:
            return "warning"
        return "normal"

    @rx.var(cache=True)
    def assignments_count(self) -> int:
        return len(self.assignments)

    @rx.var(cache=True)
    def patients_count(self) -> int:
        return len(self.patients)

    @rx.var(cache=True)
    def hospitals_count(self) -> int:
        return len(self.hospitals)

    @rx.var(cache=True)
    def ambulances_count(self) -> int:
        return len(self.ambulances)

    @rx.var(cache=True)
    def hospital_colors(self) -> dict[str, str]:
        """Assign stable, maximally distinct colors to each hospital.

        Colors are derived from sorted hospital IDs so they stay
        consistent across data refreshes.
        """
        color_map: dict[str, str] = {}
        sorted_ids = sorted(h_id for h in self.hospitals if (h_id := h.get("id")) is not None)
        num_hospitals = len(sorted_ids)
        if num_hospitals == 0:
            return color_map

        # Use a fixed seed so the palette is deterministic
        colors = distinctipy.get_colors(num_hospitals, pastel_factor=0.3, rng=42)

        for idx, hospital_id in enumerate(sorted_ids):
            rgb = colors[idx]
            hex_color = "#{:02x}{:02x}{:02x}".format(int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255))
            color_map[hospital_id] = hex_color

        return color_map

    @rx.var(cache=True)
    def patients_with_colors(self) -> list[dict[str, Any]]:
        """Enrich active patients (not delivered) with color and assignment info."""
        assignments_by_patient = {a.get("patient_id"): a for a in self._current_assignments() if a.get("patient_id")}
        hospital_colors = self.hospital_colors or {}
        hospitals_by_id = {h.get("id"): h for h in self.hospitals if h.get("id")}
        result = []
        for patient in self.patients:
            if patient.get("status") == "delivered":
                continue  # already at hospital, hide from map
            patient_id = patient.get("id")
            assignment = assignments_by_patient.get(patient_id)
            color = "#6b7280"  # gray default
            hospital_name = ""
            if assignment:
                hospital_id = assignment.get("hospital_id")
                if hospital_id:
                    color = hospital_colors.get(hospital_id, "#6b7280")
                    hosp = hospitals_by_id.get(hospital_id)
                    if hosp:
                        hospital_name = hosp.get("name") or ""
            badge_type = self._compute_badge_type(assignment) if assignment else "assigned"
            result.append({**patient, "color": color, "hospital_name": hospital_name, "badge_type": badge_type})
        return result

    @rx.var(cache=True)
    def ambulances_with_colors(self) -> list[dict[str, Any]]:
        """Enrich ambulances with color, hospital name, patient info."""
        assignments_by_ambulance: dict[str, dict[str, Any]] = {}
        for assgn in self._current_assignments():
            amb_id = assgn.get("ambulance_id")
            if amb_id and amb_id not in assignments_by_ambulance:
                assignments_by_ambulance[amb_id] = assgn
        hospital_colors = self.hospital_colors or {}
        hospitals_by_id = {h.get("id"): h for h in self.hospitals if h.get("id")}
        patients_by_id = {p.get("id"): p for p in self.patients if p.get("id")}
        result = []
        for ambulance in self.ambulances:
            ambulance_id: str = ambulance["id"]
            assignment: dict[str, Any] | None = assignments_by_ambulance.get(ambulance_id)
            color = "#6b7280"  # gray default
            hospital_name = ""
            patient_name = ""
            is_carrying = False
            if assignment:
                hospital_id = assignment.get("hospital_id")
                if hospital_id:
                    color = hospital_colors.get(hospital_id, "#6b7280")
                    hosp = hospitals_by_id.get(hospital_id)
                    if hosp:
                        hospital_name = hosp.get("name") or ""
            # Check if this ambulance is actively carrying a patient
            assigned_pid = ambulance.get("assigned_patient_id")
            if assigned_pid:
                p = patients_by_id.get(assigned_pid)
                if p:
                    patient_name = p.get("name") or ""
                    is_carrying = p.get("status") == "in_transit"
            result.append(
                {
                    **ambulance,
                    "color": color,
                    "hospital_name": hospital_name,
                    "patient_name": patient_name,
                    "is_carrying": is_carrying,
                }
            )
        return result

    @rx.var(cache=True)
    def hospitals_with_colors(self) -> list[dict[str, Any]]:
        """Enrich hospitals with their assigned color."""
        hospital_colors = self.hospital_colors or {}
        result = []
        for hospital in self.hospitals:
            hospital_id = hospital.get("id")
            color = hospital_colors.get(hospital_id, "#6b7280") if hospital_id else "#6b7280"
            result.append({**hospital, "color": color})
        return result
