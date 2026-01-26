from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(BaseSettings):
    """
    A class representing the environment variables and settings for the hospitopt application.

    Attributes:
        LOG_LEVEL (Literal["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]): The level of logging for the application.
        CONFIG_FILE_PATH (Path): The path to the configuration file for hospitopt.
    """

    LOG_LEVEL: Literal["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    CONFIG_FILE_PATH: Path

    model_config = SettingsConfigDict(env_file=".env", extra="allow")
