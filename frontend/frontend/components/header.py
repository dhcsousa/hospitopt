import reflex as rx

from frontend.states.dashboard_state import DashboardState


def header() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.h1("HospitOPT Command Center", class_name="text-2xl font-semibold text-slate-900"),
            rx.el.p("Live response overview", class_name="text-sm text-slate-500"),
            class_name="flex flex-col",
        ),
        rx.badge(
            rx.cond(
                DashboardState.api_status == "online",
                "API Online",
                rx.cond(
                    DashboardState.api_status == "offline",
                    "API Offline",
                    "Checking...",
                ),
            ),
            color_scheme=rx.cond(
                DashboardState.api_status == "online",
                "green",
                rx.cond(DashboardState.api_status == "offline", "red", "yellow"),
            ),
        ),
        class_name="flex flex-wrap items-center justify-between gap-3",
    )
