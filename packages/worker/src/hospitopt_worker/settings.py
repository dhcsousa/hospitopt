"""Worker application settings."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, Field, HttpUrl, SecretStr
from hospitopt_core.config.settings import BaseAppConfig, DbConnectionConfig, FromEnv


class APIIngestion(BaseModel):
    type: Literal["api"] = "api"
    host: FromEnv[HttpUrl]
    api_key: FromEnv[SecretStr] | None = None


class DBIngestion(DbConnectionConfig):
    type: Literal["db"] = "db"


type IngestionConfig = Annotated[
    DBIngestion | APIIngestion,
    Discriminator("type"),
]


class GoogleRoutingConfig(BaseModel):
    """Google Maps Routes API backend."""

    backend: Literal["google"] = "google"
    api_key: FromEnv[SecretStr] = Field(description="Google Maps API key.")


class ValhallaRoutingConfig(BaseModel):
    """Self-hosted Valhalla routing backend (free, time-aware)."""

    backend: Literal["valhalla"] = "valhalla"
    url: FromEnv[HttpUrl] = Field(
        default="http://localhost:8002",
        description="Base URL of the Valhalla server.",
    )
    costing: FromEnv[str] = Field(
        default="auto",
        description="Valhalla costing model (auto, bicycle, pedestrian, etc.).",
    )


type RoutingConfig = Annotated[
    GoogleRoutingConfig | ValhallaRoutingConfig,
    Discriminator("backend"),
]


class OptimizationConfig(BaseModel):
    """Tuning knobs for the optimization solver."""

    allow_reassign_in_transit: FromEnv[bool] = Field(
        False,
        description=(
            "When True, patients already picked up (in_transit) are still "
            "considered for re-optimization.  Enable for mass-casualty "
            "scenarios where a higher-priority patient may appear."
        ),
    )
    speed_factor: FromEnv[float] = Field(
        1.3,
        gt=0,
        description=(
            "Multiplier applied to travel times to account for priority "
            "vehicle speedups. 1.3 means ambulances are assumed 30%% faster "
            "than normal traffic."
        ),
    )
    allow_hospital_reassignment: FromEnv[bool] = Field(
        True,
        description=(
            "When True (default), the optimizer may change which hospital "
            "a patient is routed to on every run, even after pickup.  "
            "When False, the assigned hospital is locked once the patient "
            "is picked up (status = in_transit)."
        ),
    )


class WorkerConfig(BaseAppConfig):
    model_config = ConfigDict(extra="forbid")

    poll_interval_seconds: FromEnv[float] = Field(10.0, gt=0, description="Polling interval in seconds.")
    routing: RoutingConfig = Field(description="Routing backend configuration.")
    ingestion: IngestionConfig = Field(description="Ingestion configuration.")
    sync_inputs_to_db: bool = Field(
        True, description="Write ingested data to the worker DB. Disable when ingestion reads from the same database."
    )
    optimization: OptimizationConfig = Field(
        default_factory=OptimizationConfig, description="Optimization solver settings."
    )
