import reflex as rx

from frontend.components.assignments_panel import assignments_panel
from frontend.components.chat_widget import chat_widget
from frontend.components.header import header
from frontend.components.map_view import map_view
from frontend.components.metric_card import metric_card
from frontend.components.sidebar import sidebar
from frontend.components.sitrep_panel import sitrep_panel
from frontend.states.dashboard_state import DashboardState


def map_panel() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            metric_card(
                "Assigned ambulances",
                DashboardState.allocated_ambulance_pct,
                "Allocated",
                DashboardState.allocated_ambulance_alert_level,
            ),
            metric_card(
                "Patients in danger",
                DashboardState.patients_without_timely_response,
                "At risk of missing deadline",
                DashboardState.patients_in_danger_alert_level,
            ),
            metric_card(
                "Occupied hospital beds",
                DashboardState.occupied_beds_pct,
                "In use",
                DashboardState.occupied_beds_alert_level,
            ),
            class_name="grid grid-cols-1 gap-4 md:grid-cols-3",
        ),
        rx.el.div(
            map_view(),
            class_name="flex-1 rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden",
        ),
        class_name="mt-4 flex flex-1 flex-col gap-4",
    )


def index() -> rx.Component:
    return rx.el.div(
        sidebar(),
        rx.el.main(
            rx.el.div(
                header(),
                rx.cond(
                    DashboardState.error_message != "",
                    rx.el.p(DashboardState.error_message, class_name="text-sm text-rose-600"),
                    rx.el.span(),
                ),
                rx.cond(
                    DashboardState.is_loading,
                    rx.el.p("Loading data...", class_name="text-sm text-slate-500"),
                    rx.el.span(),
                ),
                rx.cond(
                    DashboardState.selected_tab == "map",
                    map_panel(),
                    rx.cond(
                        DashboardState.selected_tab == "table",
                        assignments_panel(),
                        sitrep_panel(),
                    ),
                ),
                # Chat widget available on map & assignments tabs
                rx.cond(
                    DashboardState.selected_tab != "sitrep",
                    chat_widget(),
                    rx.fragment(),
                ),
                class_name="mx-auto w-full max-w-6xl flex flex-col space-y-4 p-6 h-[calc(100vh-2rem)] overflow-hidden",
            ),
            on_mount=[
                DashboardState.start_health_check_polling,
                DashboardState.start_data_polling,
                DashboardState.start_position_polling,
            ],
            class_name="flex-1 bg-slate-50",
        ),
        class_name="flex h-screen",
    )
