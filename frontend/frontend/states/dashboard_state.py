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
    map_center_lat: float = 38.946
    map_center_lon: float = -9.331
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

    async def check_api_health(self) -> None:
        """Check if the API backend is online by pinging the health endpoint."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{API_BASE_URL}/health")
                if response.status_code == 200:
                    self.api_status = "online"
                else:
                    self.api_status = "offline"
        except httpx.HTTPError:
            self.api_status = "offline"

    @rx.event(background=True)
    async def start_health_check_polling(self) -> None:
        """Background task that polls API health every second."""
        while True:
            async with self:
                await self.check_api_health()
            await asyncio.sleep(1)

    @rx.event(background=True)
    async def start_data_polling(self) -> None:
        """Background task that refreshes data every 5 seconds."""
        while True:
            async with self:
                await self.load_data()
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

    @rx.var(cache=True)
    def priority_assignments(self) -> list[dict[str, Any]]:
        def sort_key(assignment: dict[str, Any]) -> int:
            deadline = assignment.get("treatment_deadline_minutes")
            return deadline if deadline is not None else 10**9

        urgent_only = [assignment for assignment in self.assignments if assignment.get("requires_urgent_transport")]
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

        return sorted(self.assignments, key=sort_key)

    @rx.var(cache=True)
    def allocated_ambulance_pct(self) -> str:
        total = len(self.ambulances)
        if total == 0:
            return "0%"
        busy = sum(1 for a in self.ambulances if a.get("assigned_patient_id"))
        return f"{(busy / total) * 100:.1f}%"

    @rx.var(cache=True)
    def patients_without_timely_response(self) -> int:
        if not self.patients:
            return 0

        assignments_by_patient = {
            assignment.get("patient_id"): assignment for assignment in self.assignments if assignment.get("patient_id")
        }
        without_timely = 0
        for patient in self.patients:
            assignment = assignments_by_patient.get(patient.get("id"))
            if assignment is None:
                without_timely += 1
                continue
            slack = assignment.get("deadline_slack_minutes")
            if assignment.get("ambulance_id") is None or (slack is not None and slack < 0):
                without_timely += 1
        return without_timely

    @rx.var(cache=True)
    def occupied_beds_pct(self) -> str:
        total_beds = sum(hospital.get("bed_capacity") or 0 for hospital in self.hospitals)
        if total_beds == 0:
            return "0%"
        used_beds = sum(hospital.get("used_beds") or 0 for hospital in self.hospitals)
        return f"{(used_beds / total_beds) * 100:.1f}%"

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
        assignments_by_patient = {a.get("patient_id"): a for a in self.assignments if a.get("patient_id")}
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
            result.append({**patient, "color": color, "hospital_name": hospital_name})
        return result

    @rx.var(cache=True)
    def ambulances_with_colors(self) -> list[dict[str, Any]]:
        """Enrich ambulances with color, hospital name, patient info."""
        assignments_by_ambulance = {a.get("ambulance_id"): a for a in self.assignments if a.get("ambulance_id")}
        hospital_colors = self.hospital_colors or {}
        hospitals_by_id = {h.get("id"): h for h in self.hospitals if h.get("id")}
        patients_by_id = {p.get("id"): p for p in self.patients if p.get("id")}
        result = []
        for ambulance in self.ambulances:
            ambulance_id = ambulance.get("id")
            assignment = assignments_by_ambulance.get(ambulance_id)
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
