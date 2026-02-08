"""Worker application settings."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, Field, HttpUrl, SecretStr
from hospitopt_core.config.settings import BaseAppConfig, DbConnectionConfig, FromEnv


class APIIngestion(BaseModel):
    type: Literal["api"] = "api"
    host: HttpUrl
    api_key: SecretStr


class DBIngestion(DbConnectionConfig):
    type: Literal["db"] = "db"


type IngestionConfig = Annotated[
    DBIngestion | APIIngestion,
    Discriminator("type"),
]


class WorkerConfig(BaseAppConfig):
    model_config = ConfigDict(extra="forbid")

    poll_interval_seconds: FromEnv[float] = Field(10.0, gt=0, description="Polling interval in seconds.")
    google_maps_api_key: FromEnv[SecretStr] = Field(description="Google Maps API key.")
    ingestion: IngestionConfig = Field(description="Ingestion configuration, only db type is supported for now.")
