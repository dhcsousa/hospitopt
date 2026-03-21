"""Floating chat widget available on Map and Assignments tabs."""

from typing import Any, cast

import reflex as rx

from frontend.states.agent_state import AgentState


def _message_bubble(msg: dict[str, str]) -> rx.Component:
    """Render a single chat bubble."""
    is_user = msg["role"] == "user"
    return rx.el.div(
        rx.cond(
            is_user,
            # User message – right-aligned, blue
            rx.el.div(
                rx.el.p(msg["content"], class_name="text-sm text-white"),
                class_name="max-w-[80%] ml-auto rounded-xl rounded-br-sm bg-blue-600 px-3 py-2",
            ),
            # Assistant message – left-aligned, rendered as markdown
            rx.el.div(
                rx.markdown(msg["content"], class_name="prose prose-sm max-w-none text-slate-800"),
                class_name="max-w-[80%] rounded-xl rounded-bl-sm bg-slate-100 px-3 py-2",
            ),
        ),
        class_name="mb-2",
    )


def chat_widget() -> rx.Component:
    """Collapsible chat panel anchored to the bottom-right."""
    return rx.el.div(
        # ── Toggle button ──────────────────────────────────
        rx.el.button(
            rx.cond(
                AgentState.chat_visible,
                rx.icon(tag="x", size=22, class_name="text-white"),
                rx.icon(tag="message-circle", size=22, class_name="text-white"),
            ),
            on_click=AgentState.toggle_chat,
            class_name="flex h-12 w-12 items-center justify-center rounded-full bg-blue-600 shadow-lg hover:bg-blue-700",
        ),
        # ── Chat panel ─────────────────────────────────────
        rx.cond(
            AgentState.chat_visible,
            rx.el.div(
                # Header
                rx.el.div(
                    rx.el.p("Ask about the data", class_name="text-sm font-semibold text-slate-900"),
                    rx.el.button(
                        rx.icon(tag="trash-2", size=14, class_name="text-slate-400"),
                        on_click=AgentState.clear_chat,
                        class_name="hover:text-slate-600",
                    ),
                    class_name="flex items-center justify-between border-b border-slate-200 px-4 py-3",
                ),
                # Messages
                rx.el.div(
                    rx.cond(
                        AgentState.chat_messages.length() > 0,  # type: ignore[union-attr]
                        rx.foreach(AgentState.chat_messages, _message_bubble),
                        rx.el.p(
                            "Ask anything about the current situation.",
                            class_name="text-xs text-slate-400 text-center mt-8",
                        ),
                    ),
                    class_name="flex-1 overflow-y-auto px-4 py-3 space-y-1",
                ),
                # Input
                rx.el.form(
                    rx.el.div(
                        rx.el.input(
                            name="question",
                            placeholder="Type a question…",
                            auto_complete="off",
                            disabled=AgentState.chat_processing,
                            class_name="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400",
                        ),
                        rx.el.button(
                            rx.cond(
                                AgentState.chat_processing,
                                rx.spinner(size="1"),
                                rx.icon(tag="send", size=16),
                            ),
                            type="submit",
                            disabled=AgentState.chat_processing,
                            class_name="ml-2 flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50",
                        ),
                        class_name="flex items-center px-3 py-2 border-t border-slate-200",
                    ),
                    reset_on_submit=True,
                    on_submit=cast(Any, AgentState).send_chat_message,
                ),
                class_name="mb-2 flex flex-col w-80 h-[28rem] rounded-2xl border border-slate-200 bg-white shadow-xl overflow-hidden",
            ),
        ),
        class_name="fixed bottom-6 right-6 z-[10000] flex flex-col items-end gap-2",
    )
