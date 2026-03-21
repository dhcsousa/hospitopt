"""API application settings."""

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr

from hospitopt_core.config.settings import BaseAppConfig, FromEnv


class CorsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allow_origins: list[HttpUrl] = Field(default_factory=list, description="Allowed origins for CORS.")
    allow_credentials: bool = Field(True, description="Allow credentials in CORS requests.")
    allow_methods: list[str] = Field(default_factory=lambda: ["GET", "OPTIONS"], description="Allowed HTTP methods.")
    allow_headers: list[str] = Field(default_factory=lambda: ["*"], description="Allowed headers.")


DEFAULT_SITREP_PROMPT = (
    "You are the AI Incident Commander Assistant for HospitOPT, an emergency medical "
    "resource optimization system used during mass casualty events (MCEs).\n"
    "\n"
    "Your role:\n"
    "- Provide clear, actionable intelligence to emergency coordinators.\n"
    "- Summarize the current situation when asked (SITREP format).\n"
    "- Identify critical patients who are running out of time.\n"
    "- Flag hospitals nearing capacity.\n"
    "- Recommend actions based on real-time data.\n"
    "\n"
    "You have access to tools that query live operational data. Use them to answer "
    "questions accurately. Always cite numbers from the data — never guess.\n"
    "\n"
    "When generating a SITREP, use this format:\n"
    "  SITREP — [timestamp]\n"
    "  1. SITUATION: Overall summary\n"
    "  2. PATIENTS: Total, assigned, unassigned, urgent\n"
    "  3. HOSPITALS: Capacity status, which are near full\n"
    "  4. AMBULANCES: Deployed vs idle\n"
    "  5. CRITICAL: Patients with <5 min deadline slack\n"
    "  6. RECOMMENDATIONS: Actionable next steps\n"
    "\n"
    "Be concise, direct, and professional — like a military operations briefing.\n"
)

DEFAULT_CHAT_PROMPT = (
    "You are the HospitOPT Chat Assistant embedded in the operations dashboard.\n"
    "\n"
    "The user is an emergency coordinator viewing a specific screen in the dashboard.\n"
    "Each message includes a JSON context snapshot of what is currently visible on screen "
    "(e.g. map markers, assignment rows, metrics).\n"
    "\n"
    "Your job:\n"
    "- Answer questions about the data the user is looking at.\n"
    "- Explain what values mean (e.g. deadline slack, urgent transport flag).\n"
    "- Highlight anomalies or concerns visible in the context.\n"
    "- Keep answers short and relevant to the current view.\n"
    "\n"
    "Do NOT make up data. If the answer is not in the provided context, say so.\n"
)


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str = Field("qwen3.5:27b", description="PydanticAI model identifier (e.g. 'qwen3.5:27b').")
    api_key: FromEnv[SecretStr] | None = Field(
        None, description="API key for the LLM provider. Required for OpenAI, not needed for Ollama."
    )
    base_url: HttpUrl = Field(
        None, description="Base URL for the LLM provider (e.g. 'http://localhost:11434/v1' for Ollama)."
    )
    system_prompt: str = Field(description="System prompt for the agent.")


class AgentsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sitrep: AgentConfig = Field(
        default_factory=lambda: AgentConfig(system_prompt=DEFAULT_SITREP_PROMPT),
        description="SITREP agent configuration.",
    )
    chat: AgentConfig = Field(
        default_factory=lambda: AgentConfig(system_prompt=DEFAULT_CHAT_PROMPT),
        description="Chat Q&A agent configuration.",
    )


class APIConfig(BaseAppConfig):
    model_config = ConfigDict(extra="forbid")

    api_key: FromEnv[SecretStr] = Field(description="API key for authentication.")
    cors: CorsConfig = Field(default_factory=CorsConfig, description="CORS configuration.")
    agents: AgentsConfig = Field(default_factory=AgentsConfig, description="Agent configurations.")
