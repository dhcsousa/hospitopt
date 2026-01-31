import os
import re
from pathlib import Path
from typing import Annotated, Any, Callable, Literal, cast

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, HttpUrl, SecretStr
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from typing_extensions import AsyncContextManager

from hospitopt_core.config.logging import LoggingConfig


class EnvParser:
    """Callable to parse and resolve env(...) placeholders in configuration values."""

    def __init__(self, load_env: bool = True) -> None:
        if load_env:
            load_dotenv()

        self._pattern = re.compile(r"ENV\(\s*[\"']?([A-Za-z_][A-Za-z0-9_.-]*)[\"']?\s*\)")

    def __call__(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value

        matches = self._pattern.findall(value)

        if len(matches) == 1:
            env_val = os.environ.get(matches[0])
            if env_val is None:
                raise RuntimeError(f"Key {matches[0]} missing from environment variables.")
            return env_val

        return value


type FromEnv[T] = Annotated[T, BeforeValidator(EnvParser())]


class DbConnectionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: FromEnv[str] = Field(description="Database hostname.")
    port: FromEnv[int] = Field(5432, description="Database port, defaults to 5432.")
    database: FromEnv[str] = Field(description="Database name.")
    user: FromEnv[str] = Field(description="User name to use for connection.")
    password: FromEnv[SecretStr] = Field(description="Password to use for connection.")

    pool_size: int = Field(10, description="Connection pool size.")

    def connection_string(self, scheme: str = "postgresql+asyncpg") -> str:
        return f"{scheme}://{self.user}:{self.password.get_secret_value()}@{self.host}:{self.port}/{self.database}"

    def to_engine_session_factory(
        self,
    ) -> tuple["AsyncEngine", Callable[[], AsyncContextManager["AsyncSession", None]]]:  # pragma: no cover
        """Create an async engine and session factory for SQLAlchemy."""

        engine: AsyncEngine = create_async_engine(
            self.connection_string(),
            pool_pre_ping=True,
            pool_size=self.pool_size,
        )

        session_factory = sessionmaker(
            bind=engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            class_=AsyncSession,
        )

        return engine, session_factory


class IngestionConfig(DbConnectionConfig):
    type: Literal["db"] = Field("db", description="Ingestion backend type.")


class WorkerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    poll_interval_seconds: FromEnv[float] = Field(10.0, gt=0, description="Polling interval in seconds.")
    google_maps_api_key: FromEnv[SecretStr] = Field(description="Google Maps API key.")
    db_connection: DbConnectionConfig = Field(description="Database connection used by the worker.")


class CorsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allow_origins: list[HttpUrl] = Field(default_factory=list, description="Allowed origins for CORS.")
    allow_credentials: bool = Field(True, description="Allow credentials in CORS requests.")
    allow_methods: list[str] = Field(default_factory=lambda: ["GET", "OPTIONS"], description="Allowed HTTP methods.")
    allow_headers: list[str] = Field(default_factory=lambda: ["*"], description="Allowed headers.")


class APIConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key: FromEnv[SecretStr] = Field(description="API key for authentication.")
    cors: CorsConfig = Field(default_factory=CorsConfig, description="CORS configuration.")


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingestion: IngestionConfig
    worker: WorkerConfig
    api: APIConfig
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @classmethod
    def from_yaml(cls, path: str | Path, load_env: bool = True) -> "AppConfig":
        """Load configuration from a YAML file and resolve env(...) placeholders."""
        yaml_path = Path(path)
        if not yaml_path.exists():
            raise FileNotFoundError(f"Config file not found: {yaml_path}")

        if load_env:
            load_dotenv()

        data = yaml.safe_load(yaml_path.read_text()) or {}
        return cast("AppConfig", cls.model_validate(data))

    @classmethod
    def export_json_schema(cls, output_path: str | Path | None = None) -> dict[str, Any]:
        """Export the JSON schema for the AppConfig model.

        Args:
            output_path: Optional path to save the schema as a JSON file.
                        If None, only returns the schema dict.

        Returns:
            The JSON schema as a dictionary.

        Example:
            # Get schema as dict
            schema = AppConfig.export_json_schema()

            # Save schema to file
            AppConfig.export_json_schema("schema/app_config_schema.json")
        """
        import json

        schema = cast(dict[str, Any], cls.model_json_schema())

        if output_path is not None:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(json.dumps(schema, indent=2))

        return schema
