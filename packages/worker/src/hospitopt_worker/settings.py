"""Worker application settings."""

from typing import Literal

from pydantic import ConfigDict, Field, SecretStr
from hospitopt_core.config.settings import BaseAppConfig, DbConnectionConfig, FromEnv


class IngestionConfig(DbConnectionConfig):
    type: Literal["db"] = Field("db", description="Ingestion backend type.")


class WorkerConfig(BaseAppConfig):
    model_config = ConfigDict(extra="forbid")

    poll_interval_seconds: FromEnv[float] = Field(10.0, gt=0, description="Polling interval in seconds.")
    google_maps_api_key: FromEnv[SecretStr] = Field(description="Google Maps API key.")
    ingestion: IngestionConfig = Field(description="Ingestion configuration, only db type is supported for now.")
