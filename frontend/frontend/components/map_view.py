import reflex as rx
import reflex_enterprise as rxe
from reflex.vars.base import Var

from frontend.states.dashboard_state import DashboardState


def _create_colored_div_icon(color_var: Var, icon_type: str, size: tuple[int, int]) -> Var:
    """Create a colored div icon using Leaflet's divIcon."""
    # Use emoji or simple HTML for different icon types
    icon_html_map = {
        "hospital": "🏥",
        "patient": "🤕",
        "ambulance": "🚑",
    }

    icon_emoji = icon_html_map.get(icon_type, "📍")

    # Create JavaScript expression that creates a divIcon with colored background
    js_expr = f"""window.L && window.L.divIcon({{
        html: `<div style="background-color: ${{({str(color_var)}) || '#6b7280'}}; width: {size[0]}px; height: {size[1]}px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 18px; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">{icon_emoji}</div>`,
        className: '',
        iconSize: [{size[0]}, {size[1]}],
        iconAnchor: [{size[0] // 2}, {size[1]}]
    }})"""

    return Var(_js_expr=js_expr)


def map_view() -> rx.Component:
    return rxe.map(
        rxe.map.tile_layer(
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        ),
        rx.foreach(
            DashboardState.hospitals_with_colors,
            lambda hospital: rxe.map.marker(
                rxe.map.popup(
                    rx.vstack(
                        rx.text(
                            rx.cond(hospital.get("name"), hospital.get("name"), "Hospital"),
                            weight="bold",
                        ),
                        rx.cond(
                            hospital.get("bed_capacity") is not None,
                            rx.hstack(
                                rx.text("Beds:"),
                                rx.text(hospital.get("used_beds")),
                                rx.text("/"),
                                rx.text(hospital.get("bed_capacity")),
                                spacing="1",
                            ),
                            rx.text("Beds: —"),
                        ),
                        spacing="1",
                    )
                ),
                position=rxe.map.latlng(lat=hospital["lat"], lng=hospital["lon"]),
                custom_attrs={"icon": _create_colored_div_icon(hospital["color"], "hospital", (40, 40))},
            ),
        ),
        rx.foreach(
            DashboardState.patients_with_colors,
            lambda patient: rxe.map.marker(
                rxe.map.popup(
                    rx.vstack(
                        rx.text("Patient", weight="bold"),
                        rx.hstack(
                            rx.text("Time to hospital:"),
                            rx.text(
                                rx.cond(
                                    patient.get("time_to_hospital_minutes"),
                                    patient.get("time_to_hospital_minutes"),
                                    "—",
                                )
                            ),
                            rx.text(
                                rx.cond(
                                    patient.get("time_to_hospital_minutes"),
                                    " min",
                                    "",
                                )
                            ),
                            spacing="1",
                        ),
                        spacing="1",
                    )
                ),
                position=rxe.map.latlng(lat=patient["lat"], lng=patient["lon"]),
                custom_attrs={"icon": _create_colored_div_icon(patient["color"], "patient", (40, 40))},
            ),
        ),
        rx.foreach(
            DashboardState.ambulances_with_colors,
            lambda ambulance: rxe.map.marker(
                rxe.map.popup(
                    rx.vstack(
                        rx.text("Ambulance", weight="bold"),
                        rx.hstack(
                            rx.text("Assigned:"),
                            rx.text(
                                rx.cond(
                                    ambulance.get("assigned_patient_id"),
                                    ambulance.get("assigned_patient_id"),
                                    "—",
                                )
                            ),
                            spacing="1",
                        ),
                        spacing="1",
                    )
                ),
                position=rxe.map.latlng(lat=ambulance["lat"], lng=ambulance["lon"]),
                custom_attrs={"icon": _create_colored_div_icon(ambulance["color"], "ambulance", (40, 40))},
            ),
        ),
        id="assignments-map",
        center=rxe.map.latlng(lat=DashboardState.map_center_lat, lng=DashboardState.map_center_lon),
        zoom=DashboardState.map_zoom,
        height="460px",
        width="100%",
    )
