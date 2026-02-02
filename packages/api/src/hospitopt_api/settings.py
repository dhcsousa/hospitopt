"""API application settings."""

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr

from hospitopt_core.config.settings import BaseAppConfig, FromEnv


class CorsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allow_origins: list[HttpUrl] = Field(default_factory=list, description="Allowed origins for CORS.")
    allow_credentials: bool = Field(True, description="Allow credentials in CORS requests.")
    allow_methods: list[str] = Field(default_factory=lambda: ["GET", "OPTIONS"], description="Allowed HTTP methods.")
    allow_headers: list[str] = Field(default_factory=lambda: ["*"], description="Allowed headers.")


class APIConfig(BaseAppConfig):
    model_config = ConfigDict(extra="forbid")

    api_key: FromEnv[SecretStr] = Field(description="API key for authentication.")
    cors: CorsConfig = Field(default_factory=CorsConfig, description="CORS configuration.")
