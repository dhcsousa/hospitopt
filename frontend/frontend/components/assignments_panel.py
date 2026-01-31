import reflex as rx

from frontend.states.dashboard_state import DashboardState
from frontend.components.assignment_tables import assignments_table, priority_table


def assignments_panel() -> rx.Component:
    return rx.el.div(
        rx.tabs.root(
            rx.tabs.list(
                rx.tabs.trigger(
                    rx.hstack(
                        rx.icon("alert-triangle", size=18, class_name="text-slate-900"),
                        rx.el.span("Priority", class_name="text-sm font-semibold text-slate-900"),
                        spacing="2",
                        align="center",
                    ),
                    value="priority",
                ),
                rx.tabs.trigger(
                    rx.hstack(
                        rx.icon("list", size=18, class_name="text-slate-900"),
                        rx.el.span("All Assignments", class_name="text-sm font-semibold text-slate-900"),
                        spacing="2",
                        align="center",
                    ),
                    value="all",
                ),
                class_name="mt-2",
            ),
            rx.tabs.content(
                priority_table(DashboardState.priority_assignments),
                value="priority",
                margin_top="1rem",
            ),
            rx.tabs.content(
                assignments_table(DashboardState.sorted_assignments_by_slack),
                value="all",
                margin_top="1rem",
            ),
            default_value="priority",
        ),
        class_name="mt-4 flex-1 rounded-2xl border border-slate-200 bg-white shadow-sm p-4",
    )
