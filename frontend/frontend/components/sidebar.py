from typing import Any, cast

import reflex as rx

from ..states.dashboard_state import DashboardState


def sidebar() -> rx.Component:
    return rx.el.aside(
        rx.el.div(
            rx.el.div(
                "HO",
                class_name="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-600 text-white font-bold",
            ),
            rx.el.div(
                rx.el.p("HospitOPT", class_name="text-sm font-semibold text-slate-900"),
                rx.el.p("Operations", class_name="text-xs text-slate-500"),
                class_name="flex flex-col",
            ),
            class_name="flex items-center gap-3 border-b border-slate-200 px-6 py-4",
        ),
        rx.el.nav(
            rx.el.button(
                rx.icon(tag="map", size=18, class_name="mr-3"),
                "Map",
                on_click=cast(Any, DashboardState).set_tab("map"),
                class_name=rx.cond(
                    DashboardState.selected_tab == "map",
                    "flex items-center rounded-lg px-3 py-2 text-sm font-medium text-blue-600 bg-blue-50",
                    "flex items-center rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100",
                ),
            ),
            rx.el.button(
                rx.icon(tag="table", size=18, class_name="mr-3"),
                "Assignments",
                on_click=cast(Any, DashboardState).set_tab("table"),
                class_name=rx.cond(
                    DashboardState.selected_tab == "table",
                    "flex items-center rounded-lg px-3 py-2 text-sm font-medium text-blue-600 bg-blue-50",
                    "flex items-center rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100",
                ),
            ),
            class_name="flex flex-col gap-1 px-4 py-4",
        ),
        class_name="hidden lg:flex lg:flex-col lg:w-64 lg:h-screen lg:border-r lg:border-slate-200 bg-white",
    )
