"""SITREP panel – tabbed view displaying a structured situation report."""

from typing import Any, cast

import reflex as rx

from frontend.states.agent_state import AgentState, SITREP_SECTIONS


def _tab_button(key: str, label: str, icon_tag: str) -> rx.Component:
    """A single tab button that highlights when active."""
    return rx.el.button(
        rx.icon(tag=icon_tag, size=14, class_name="mr-1.5 shrink-0"),
        rx.el.span(label),
        on_click=cast(Any, AgentState).set_sitrep_tab(key),
        class_name=rx.cond(
            AgentState.sitrep_active_tab == key,
            "inline-flex items-center rounded-lg px-3 py-1.5 text-xs font-semibold bg-blue-600 text-white",
            "inline-flex items-center rounded-lg px-3 py-1.5 text-xs font-medium text-slate-600 bg-slate-100 hover:bg-slate-200",
        ),
    )


def sitrep_panel() -> rx.Component:
    return rx.el.div(
        # ── Toolbar ─────────────────────────────────────────
        rx.el.div(
            rx.el.span(
                "Situation Report",
                class_name="text-sm font-semibold text-slate-700",
            ),
            rx.el.div(
                # Timestamp
                rx.cond(
                    AgentState.sitrep_generated_at != "",
                    rx.el.span(
                        AgentState.sitrep_generated_at,
                        class_name="text-xs text-slate-400",
                    ),
                    rx.fragment(),
                ),
                # Refresh button
                rx.el.button(
                    rx.cond(
                        AgentState.sitrep_loading,
                        rx.spinner(size="1"),
                        rx.icon(tag="refresh-cw", size=14),
                    ),
                    on_click=AgentState.force_generate_sitrep,
                    disabled=AgentState.sitrep_loading,
                    title="Regenerate SITREP",
                    class_name="inline-flex items-center justify-center rounded-md p-1.5 text-slate-400 hover:text-blue-600 hover:bg-slate-100 disabled:opacity-50 disabled:cursor-not-allowed",
                ),
                class_name="flex items-center gap-2",
            ),
            class_name="flex items-center justify-between",
        ),
        # ── Error ───────────────────────────────────────────
        rx.cond(
            AgentState.sitrep_error != "",
            rx.el.p(
                AgentState.sitrep_error,
                class_name="mt-2 text-sm text-rose-600",
            ),
            rx.fragment(),
        ),
        # ── Content area ────────────────────────────────────
        rx.cond(
            AgentState.sitrep_has_data,
            rx.el.div(
                # Tab bar
                rx.el.div(
                    *[_tab_button(key, label, icon) for key, label, icon in SITREP_SECTIONS],
                    class_name="flex flex-wrap gap-2 border-b border-slate-200 pb-3",
                ),
                # Active section content
                rx.el.div(
                    rx.markdown(
                        AgentState.sitrep_active_content,
                        class_name="prose prose-sm max-w-none text-slate-800",
                    ),
                    class_name="flex-1 overflow-y-auto px-1 py-4 min-h-0",
                ),
                class_name="mt-4 flex flex-1 flex-col rounded-xl border border-slate-200 bg-white p-5 shadow-sm min-h-0",
            ),
            # ── Empty / loading states ──────────────────────
            rx.cond(
                AgentState.sitrep_loading,
                rx.el.div(
                    rx.el.p(
                        "The SITREP agent is querying live data…",
                        class_name="text-sm text-slate-500",
                    ),
                    class_name="mt-4 flex flex-1 items-center justify-center",
                ),
                rx.el.div(
                    rx.el.div(
                        rx.icon(tag="file-text", size=40, class_name="text-slate-300"),
                        rx.el.p(
                            "Waiting for scenario data…",
                            class_name="text-sm text-slate-400 mt-2",
                        ),
                        class_name="flex flex-col items-center",
                    ),
                    class_name="mt-4 flex flex-1 items-center justify-center",
                ),
            ),
        ),
        class_name="mt-4 flex flex-1 flex-col min-h-0",
    )
