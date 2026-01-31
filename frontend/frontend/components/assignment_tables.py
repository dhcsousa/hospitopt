from typing import Any, cast

import reflex as rx

from frontend.states.dashboard_state import DashboardState


def assignment_row(assignment: dict[str, object]) -> rx.Component:
    return rx.el.tr(
        rx.el.td(
            rx.el.button(
                rx.cond(assignment.get("patient_id"), assignment.get("patient_id"), "—"),
                on_click=cast(Any, DashboardState).select_patient(assignment.get("patient_id")),
                class_name="text-left text-sm text-slate-900 hover:underline",
            ),
            class_name="px-4 py-2",
        ),
        rx.el.td(
            rx.el.button(
                rx.cond(assignment.get("hospital_id"), assignment.get("hospital_id"), "—"),
                on_click=cast(Any, DashboardState).select_hospital(assignment.get("hospital_id")),
                class_name="text-left text-sm text-slate-900 hover:underline",
            ),
            class_name="px-4 py-2",
        ),
        rx.el.td(
            rx.el.button(
                rx.cond(assignment.get("ambulance_id"), assignment.get("ambulance_id"), "—"),
                on_click=cast(Any, DashboardState).select_ambulance(assignment.get("ambulance_id")),
                class_name="text-left text-sm text-slate-900 hover:underline",
            ),
            class_name="px-4 py-2",
        ),
        rx.el.td(
            rx.el.span(
                rx.cond(assignment.get("estimated_travel_minutes"), assignment.get("estimated_travel_minutes"), "—"),
                rx.cond(assignment.get("estimated_travel_minutes"), " min", ""),
                class_name="text-slate-900",
            ),
            class_name="px-4 py-2 text-sm",
        ),
        rx.el.td(
            rx.el.span(
                rx.cond(assignment.get("deadline_slack_minutes"), assignment.get("deadline_slack_minutes"), "—"),
                rx.cond(assignment.get("deadline_slack_minutes"), " min", ""),
                class_name="text-slate-900",
            ),
            class_name="px-4 py-2 text-sm",
        ),
        rx.el.td(
            rx.el.span(
                rx.cond(
                    assignment.get("treatment_deadline_minutes"), assignment.get("treatment_deadline_minutes"), "—"
                ),
                rx.cond(assignment.get("treatment_deadline_minutes"), " min", ""),
                class_name="text-slate-900",
            ),
            class_name="px-4 py-2 text-sm",
        ),
        rx.el.td(
            rx.el.span(
                rx.cond(
                    assignment.get("requires_urgent_transport"),
                    "Yes",
                    "No",
                ),
                class_name=rx.cond(
                    assignment.get("requires_urgent_transport"),
                    "inline-flex rounded-full bg-rose-50 px-2 py-0.5 text-xs font-medium text-rose-700",
                    "inline-flex rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700",
                ),
            ),
            class_name="px-4 py-2",
        ),
        rx.el.td(
            rx.el.span(rx.cond(assignment.get("optimized_at"), assignment.get("optimized_at"), "—")),
            class_name="px-4 py-2 text-sm text-slate-500",
        ),
        class_name="hover:bg-slate-50",
    )


def priority_row(assignment: dict[str, object]) -> rx.Component:
    return rx.el.tr(
        rx.el.td(
            rx.el.button(
                rx.cond(assignment.get("patient_id"), assignment.get("patient_id"), "—"),
                on_click=cast(Any, DashboardState).select_patient(assignment.get("patient_id")),
                class_name="text-left text-sm text-slate-900 hover:underline",
            ),
            class_name="px-4 py-2",
        ),
        rx.el.td(
            rx.el.span(
                rx.cond(
                    assignment.get("treatment_deadline_minutes"), assignment.get("treatment_deadline_minutes"), "—"
                ),
                rx.cond(assignment.get("treatment_deadline_minutes"), " min", ""),
                class_name="text-slate-900",
            ),
            class_name="px-4 py-2 text-sm",
        ),
        rx.el.td(
            rx.el.span(rx.cond(assignment.get("optimized_at"), assignment.get("optimized_at"), "—")),
            class_name="px-4 py-2 text-sm text-slate-500",
        ),
        class_name="hover:bg-slate-50",
    )


def assignments_table(assignments: rx.Var | list[dict[str, object]]) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.table(
                    rx.el.thead(
                        rx.el.tr(
                            rx.el.th(
                                "Patient",
                                class_name="px-4 py-2 text-left text-xs font-semibold text-slate-500 bg-white sticky top-0 z-10",
                            ),
                            rx.el.th(
                                "Hospital",
                                class_name="px-4 py-2 text-left text-xs font-semibold text-slate-500 bg-white sticky top-0 z-10",
                            ),
                            rx.el.th(
                                "Ambulance",
                                class_name="px-4 py-2 text-left text-xs font-semibold text-slate-500 bg-white sticky top-0 z-10",
                            ),
                            rx.el.th(
                                "Travel",
                                class_name="px-4 py-2 text-left text-xs font-semibold text-slate-500 bg-white sticky top-0 z-10",
                            ),
                            rx.el.th(
                                "Slack",
                                class_name="px-4 py-2 text-left text-xs font-semibold text-slate-500 bg-white sticky top-0 z-10",
                            ),
                            rx.el.th(
                                "Deadline",
                                class_name="px-4 py-2 text-left text-xs font-semibold text-slate-500 bg-white sticky top-0 z-10",
                            ),
                            rx.el.th(
                                "Urgent",
                                class_name="px-4 py-2 text-left text-xs font-semibold text-slate-500 bg-white sticky top-0 z-10",
                            ),
                            rx.el.th(
                                "Optimized",
                                class_name="px-4 py-2 text-left text-xs font-semibold text-slate-500 bg-white sticky top-0 z-10",
                            ),
                        )
                    ),
                    rx.el.tbody(rx.foreach(assignments, assignment_row)),
                    class_name="min-w-full divide-y divide-slate-200",
                ),
                class_name="max-h-[420px] overflow-y-auto",
            ),
            class_name="overflow-x-auto",
        ),
        class_name="rounded-xl border border-slate-200 bg-white p-4 shadow-sm",
    )


def priority_table(assignments: rx.Var | list[dict[str, object]]) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.table(
                    rx.el.thead(
                        rx.el.tr(
                            rx.el.th(
                                "Patient",
                                class_name="px-4 py-2 text-left text-xs font-semibold text-slate-500 bg-white sticky top-0 z-10",
                            ),
                            rx.el.th(
                                "Deadline",
                                class_name="px-4 py-2 text-left text-xs font-semibold text-slate-500 bg-white sticky top-0 z-10",
                            ),
                            rx.el.th(
                                "Optimized",
                                class_name="px-4 py-2 text-left text-xs font-semibold text-slate-500 bg-white sticky top-0 z-10",
                            ),
                        )
                    ),
                    rx.el.tbody(rx.foreach(assignments, priority_row)),
                    class_name="min-w-full divide-y divide-slate-200",
                ),
                class_name="max-h-[420px] overflow-y-auto",
            ),
            class_name="overflow-x-auto",
        ),
        class_name="rounded-xl border border-slate-200 bg-white p-4 shadow-sm",
    )
