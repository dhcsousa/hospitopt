import reflex as rx
import reflex_enterprise as rxe
from reflex.vars.base import Var

from frontend.states.dashboard_state import DashboardState


def _create_colored_div_icon(
    color_var: Var,
    icon_type: str,
    size: tuple[int, int],
    is_carrying: Var | None = None,
    badge_type_var: Var | None = None,
) -> Var:
    """Create a duck-typed Leaflet icon object in pure JS (no window.L dependency)."""
    anchor_x = size[0] // 2
    anchor_y = size[1]

    if icon_type == "ambulance" and is_carrying is not None:
        # Dynamically switch emoji based on whether ambulance is carrying a patient
        emoji_expr = f"(({str(is_carrying)}) ? '🚑💨' : '🚑')"
    elif icon_type == "patient" and badge_type_var is not None:
        badge_js = str(badge_type_var)
        emoji_expr = f"(({badge_js}) === 'impossible' ? '🆘' : '🤕')"
    else:
        icon_html_map = {
            "hospital": "🏥",
            "patient": "🤕",
        }
        emoji_expr = f"'{icon_html_map.get(icon_type, '📍')}'"

    # Build the innerHTML line — impossible patients get a red glow instead of assigned-hospital color
    if icon_type == "patient" and badge_type_var is not None:
        badge_js = str(badge_type_var)
        color_js = str(color_var)
        icon_inner = f"""
            var isImpossible = ({badge_js}) === 'impossible';
            var bgColor = isImpossible ? '#dc2626' : (({color_js}) || '#6b7280');
            var boxShadow = isImpossible ? '0 0 0 2px white, 0 0 0 4px #dc2626, 0 2px 8px rgba(220,38,38,0.5)' : '0 2px 4px rgba(0,0,0,0.3)';
            div.innerHTML = `<div style="background-color: ${{bgColor}}; width: {size[0]}px; height: {size[1]}px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 18px; border: 2px solid white; box-shadow: ${{boxShadow}};">${{emoji}}</div>`;"""
    else:
        icon_inner = f"""
            div.innerHTML = `<div style="background-color: ${{({str(color_var)}) || '#6b7280'}}; width: {size[0]}px; height: {size[1]}px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 18px; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">${{emoji}}</div>`;"""

    js_expr = f"""({{
        options: {{
            iconSize: [{size[0]}, {size[1]}],
            iconAnchor: [{anchor_x}, {anchor_y}],
            popupAnchor: [0, -{anchor_y}],
            tooltipAnchor: [{anchor_x}, 0],
            className: ''
        }},
        createIcon: function(oldIcon) {{
            var div = (oldIcon && oldIcon.tagName === 'DIV') ? oldIcon : document.createElement('div');
            var emoji = {emoji_expr};{icon_inner}
            div.className = 'leaflet-marker-icon';
            div.style.width = '{size[0]}px';
            div.style.height = '{size[1]}px';
            div.style.marginLeft = '-{anchor_x}px';
            div.style.marginTop = '-{anchor_y}px';
            return div;
        }},
        createShadow: function() {{ return null; }}
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
                        rx.match(
                            patient.get("badge_type"),
                            (
                                "impossible",
                                rx.badge("⚠️ IMPOSSIBLE — manual triage needed", color_scheme="red", variant="solid"),
                            ),
                            rx.fragment(),
                        ),
                        rx.text(
                            rx.cond(patient.get("name"), patient.get("name"), "Patient"),
                            weight="bold",
                        ),
                        rx.hstack(
                            rx.text("Status:"),
                            rx.text(
                                rx.cond(
                                    patient.get("status"),
                                    patient.get("status"),
                                    "—",
                                )
                            ),
                            spacing="1",
                        ),
                        rx.hstack(
                            rx.text("Deadline:"),
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
                        rx.cond(
                            patient.get("hospital_name"),
                            rx.hstack(
                                rx.text("→"),
                                rx.text(patient.get("hospital_name")),
                                spacing="1",
                            ),
                            rx.fragment(),
                        ),
                        spacing="1",
                    )
                ),
                position=rxe.map.latlng(lat=patient["lat"], lng=patient["lon"]),
                custom_attrs={
                    "icon": _create_colored_div_icon(
                        patient["color"], "patient", (40, 40), badge_type_var=patient["badge_type"]
                    )
                },
            ),
        ),
        rx.foreach(
            DashboardState.ambulances_with_colors,
            lambda ambulance: rxe.map.marker(
                rxe.map.popup(
                    rx.vstack(
                        rx.text(
                            rx.cond(
                                ambulance.get("is_carrying"),
                                "Ambulance (carrying)",
                                "Ambulance",
                            ),
                            weight="bold",
                        ),
                        rx.cond(
                            ambulance.get("patient_name"),
                            rx.hstack(
                                rx.text("Patient:"),
                                rx.text(ambulance.get("patient_name")),
                                spacing="1",
                            ),
                            rx.fragment(),
                        ),
                        rx.cond(
                            ambulance.get("hospital_name"),
                            rx.hstack(
                                rx.text("→"),
                                rx.text(ambulance.get("hospital_name")),
                                spacing="1",
                            ),
                            rx.fragment(),
                        ),
                        spacing="1",
                    )
                ),
                position=rxe.map.latlng(lat=ambulance["lat"], lng=ambulance["lon"]),
                custom_attrs={
                    "icon": _create_colored_div_icon(
                        ambulance["color"],
                        "ambulance",
                        (40, 40),
                        is_carrying=ambulance["is_carrying"],
                    )
                },
            ),
        ),
        id="assignments-map",
        center=rxe.map.latlng(lat=DashboardState.map_center_lat, lng=DashboardState.map_center_lon),
        zoom=DashboardState.map_zoom,
        height="460px",
        width="100%",
    )
