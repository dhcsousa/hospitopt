"""State management for AI agent interactions (SITREP & Chat)."""

import json
import os
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx
import reflex as rx

if TYPE_CHECKING:
    from frontend.states.dashboard_state import DashboardState

API_BASE_URL = os.getenv("HOSPITOPT_API_URL", "").rstrip("/")
API_KEY = os.getenv("HOSPITOPT_API_KEY", "")

# Section keys in display order – must match SitrepReport field names.
SITREP_SECTIONS: list[tuple[str, str, str]] = [
    ("summary", "Summary", "file-text"),
    ("patient_overview", "Patients", "users"),
    ("hospital_capacity", "Hospitals", "building-2"),
    ("ambulance_fleet_status", "Ambulances", "ambulance"),
    ("critical_patients", "Critical", "triangle-alert"),
    ("unassigned_patients", "Unassigned", "user-x"),
    ("action_required", "Actions", "clipboard-list"),
]


def _make_run_input(
    messages: list[dict[str, str]],
    context: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    """Build an ag-ui RunAgentInput payload."""
    return {
        "threadId": str(uuid.uuid4()),
        "runId": str(uuid.uuid4()),
        "state": None,
        "messages": [{"id": str(uuid.uuid4()), "role": m["role"], "content": m["content"]} for m in messages],
        "tools": [],
        "context": context or [],
        "forwardedProps": {},
    }


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {API_KEY}",  # noqa: S105
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }


def _build_screen_context(dashboard: DashboardState) -> list[dict[str, str]]:
    """Build ag-ui Context entries from visible dashboard data."""
    return [
        {"description": "active_view", "value": dashboard.selected_tab},
        {
            "description": "map_viewport",
            "value": json.dumps(
                {
                    "center_lat": dashboard.map_center_lat,
                    "center_lon": dashboard.map_center_lon,
                    "zoom": dashboard.map_zoom,
                }
            ),
        },
        {"description": "patients", "value": json.dumps(dashboard.patients)},
        {"description": "hospitals", "value": json.dumps(dashboard.hospitals)},
        {"description": "ambulances", "value": json.dumps(dashboard.ambulances)},
        {"description": "assignments", "value": json.dumps(dashboard.assignments)},
    ]


async def _iter_text_deltas(
    client: httpx.AsyncClient,
    url: str,
    run_input: dict,
) -> AsyncGenerator[str, None]:
    """Yield text deltas from an ag-ui SSE stream."""
    async with client.stream("POST", url, json=run_input, headers=_headers()) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload.strip() == "[DONE]":
                break
            try:
                event = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "TEXT_MESSAGE_CONTENT":
                yield event.get("delta", "")


class AgentState(rx.State):
    """Manages SITREP generation and chat interactions."""

    # ── SITREP ──────────────────────────────────────────────
    sitrep_sections: dict[str, str] = {}
    sitrep_generated_at: str = ""
    sitrep_active_tab: str = "summary"
    sitrep_loading: bool = False
    sitrep_error: str = ""
    _sitrep_fingerprint: str = ""

    @rx.var(cache=True)
    def sitrep_has_data(self) -> bool:
        return len(self.sitrep_sections) > 0

    @rx.var(cache=True)
    def sitrep_active_content(self) -> str:
        return self.sitrep_sections.get(self.sitrep_active_tab, "")

    def set_sitrep_tab(self, tab: str) -> None:
        self.sitrep_active_tab = tab

    # ── Chat ────────────────────────────────────────────────
    _chat_history: list[dict[str, str]] = []
    chat_processing: bool = False
    chat_visible: bool = False

    def toggle_chat(self) -> None:
        self.chat_visible = not self.chat_visible

    @rx.var(cache=True)
    def chat_messages(self) -> list[dict[str, str]]:
        return self._chat_history

    # ── SITREP handler ──────────────────────────────────────
    @rx.event
    async def maybe_generate_sitrep(self, fingerprint: str) -> AsyncGenerator[None, None]:
        """Generate SITREP only if the underlying scenario data has changed."""
        if not fingerprint or self.sitrep_loading:
            return
        if fingerprint == self._sitrep_fingerprint:
            return
        self._sitrep_fingerprint = fingerprint
        async for _ in self._run_sitrep():
            yield

    @rx.event
    async def force_generate_sitrep(self) -> AsyncGenerator[None, None]:
        """Force-regenerate the SITREP regardless of fingerprint."""
        async for _ in self._run_sitrep():
            yield

    async def _run_sitrep(self) -> AsyncGenerator[None, None]:
        """Fetch a structured situation report from the SITREP agent."""
        self.sitrep_sections = {}
        self.sitrep_generated_at = ""
        self.sitrep_error = ""
        self.sitrep_loading = True
        self.sitrep_active_tab = "summary"
        yield

        try:
            headers = {
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient(timeout=600.0) as client:
                resp = await client.post(
                    f"{API_BASE_URL}/agents/sitrep",
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()

            self.sitrep_sections = {key: data.get(key, "") for key, _, _ in SITREP_SECTIONS}
            self.sitrep_generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        except httpx.TimeoutException:
            self.sitrep_error = (
                "The SITREP agent timed out (>600 s). The model may still be processing — try again shortly."
            )
        except httpx.HTTPStatusError as exc:
            self.sitrep_error = f"SITREP agent returned HTTP {exc.response.status_code}: {exc.response.text[:300]}"
        except httpx.HTTPError as exc:
            self.sitrep_error = f"Failed to connect to the SITREP agent: {exc}"
        finally:
            self.sitrep_loading = False

    # ── Chat handler ────────────────────────────────────────
    @rx.event
    async def send_chat_message(self, form_data: dict[str, str]) -> AsyncGenerator[None, None]:
        """Stream a response from the Chat agent."""
        question = form_data.get("question", "").strip()
        if not question:
            return

        self._chat_history.append({"role": "user", "content": question})
        self._chat_history.append({"role": "assistant", "content": ""})
        self.chat_processing = True
        yield

        # Gather current dashboard state so the agent knows what the user sees.
        from frontend.states.dashboard_state import DashboardState

        dashboard = await self.get_state(DashboardState)
        screen_context = _build_screen_context(dashboard)

        # Build message history for the agent (skip the empty placeholder).
        ag_messages = [m for m in self._chat_history if m["content"]]

        run_input = _make_run_input(ag_messages, context=screen_context)

        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                async for delta in _iter_text_deltas(client, f"{API_BASE_URL}/agents/chat", run_input):
                    self._chat_history[-1]["content"] += delta
                    self._chat_history = self._chat_history  # trigger reactivity
                    yield
        except httpx.HTTPError:
            self._chat_history[-1]["content"] = "**Error:** Failed to connect to the chat agent."
            self._chat_history = self._chat_history
        finally:
            self.chat_processing = False

    def clear_chat(self) -> None:
        self._chat_history = []
