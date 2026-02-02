from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(BaseSettings):
    """
    A class representing the environment variables and settings for the hospitopt application.

    Attributes:
        LOG_LEVEL (Literal["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]): The level of logging for the application.
        API_CONFIG_FILE_PATH (Path | None): The path to the API configuration file.
        WORKER_CONFIG_FILE_PATH (Path | None): The path to the Worker configuration file.
    """

    LOG_LEVEL: Literal["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    API_CONFIG_FILE_PATH: Path | None = None
    WORKER_CONFIG_FILE_PATH: Path | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="allow")
