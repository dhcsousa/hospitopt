"""API application settings."""

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr

from hospitopt_core.config.settings import BaseAppConfig, FromEnv


class CorsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allow_origins: list[HttpUrl] = Field(default_factory=list, description="Allowed origins for CORS.")
    allow_credentials: bool = Field(True, description="Allow credentials in CORS requests.")
    allow_methods: list[str] = Field(default_factory=lambda: ["GET", "OPTIONS"], description="Allowed HTTP methods.")
    allow_headers: list[str] = Field(default_factory=lambda: ["*"], description="Allowed headers.")


DEFAULT_SYSTEM_PROMPT = (
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


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str = Field("qwen3.5:27b", description="PydanticAI model identifier (e.g. 'qwen3.5:27b').")
    api_key: FromEnv[SecretStr] | None = Field(
        None, description="API key for the LLM provider. Required for OpenAI, not needed for Ollama."
    )
    base_url: FromEnv[str] | None = Field(
        None, description="Custom base URL for the LLM provider (e.g. 'http://localhost:11434/v1' for Ollama)."
    )
    system_prompt: str = Field(
        default=DEFAULT_SYSTEM_PROMPT, description="System prompt for the incident commander agent."
    )


class APIConfig(BaseAppConfig):
    model_config = ConfigDict(extra="forbid")

    api_key: FromEnv[SecretStr] = Field(description="API key for authentication.")
    cors: CorsConfig = Field(default_factory=CorsConfig, description="CORS configuration.")
    agent: AgentConfig = Field(default_factory=AgentConfig, description="Agent configuration.")
