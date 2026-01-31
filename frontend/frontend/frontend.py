"""HospitOPT Reflex dashboard app."""

import reflex as rx
import reflex_enterprise as rxe

from frontend.pages.index import index
from frontend.states.dashboard_state import DashboardState

base_stylesheets = [
    "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
]

base_style = {
    "font_family": "Inter",
}

app = rxe.App(
    style=base_style,
    stylesheets=base_stylesheets,
    theme=rx.theme(appearance="light", has_background=True, radius="large", accent_color="blue"),
)
app.add_page(index, route="/", on_load=DashboardState.load_data, title="HospitOPT Dashboard")
