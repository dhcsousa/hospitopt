import logging
import sys
from pathlib import Path
from types import FrameType
from typing import Annotated, Literal

from loguru import logger
from pydantic import BaseModel, Field

# Supported log levels
type LogLevel = Literal["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]


class LoggingConfig(BaseModel):
    """Logging configuration with production-grade defaults."""

    enable_file_logging: Annotated[
        bool,
        Field(False, description="Enable logging to files."),
    ]

    log_dir: Annotated[
        Path,
        Field(Path("logs"), description="Directory for log files."),
    ]

    log_file_name: Annotated[
        str,
        Field("{time:YYYY-MM-DD}.log", description="Log file name pattern."),
    ]

    rotation: Annotated[
        str,
        Field(
            "00:00",
            description="Log rotation schedule (e.g., '00:00' for daily, '1 week', '100 MB').",
        ),
    ]

    retention: Annotated[
        str,
        Field(
            "30 days",
            description="Log retention period (e.g., '30 days', '1 week').",
        ),
    ]

    compression: Annotated[
        str,
        Field(
            "zip",
            description="Compression format for rotated logs (e.g., 'zip', 'gz', 'tar.gz').",
        ),
    ]

    def setup_logging(self, *, level: LogLevel) -> None:  # pragma: no cover
        """Configure logging using Loguru."""
        logger.remove()

        logger.add(
            sys.stderr,
            level=level,
            serialize=False,
            colorize=True,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            ),
        )

        if self.enable_file_logging:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            log_path = self.log_dir / self.log_file_name
            logger.info(f"Logging to file @ {log_path}")

            logger.add(
                str(log_path),
                level=level,
                serialize=True,
                rotation=self.rotation,
                retention=self.retention,
                compression=self.compression,
                enqueue=True,
                format="{level: <8}: {message}",
            )

        logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

        logger.info(
            "Logging configured",
            extra={
                "level": level,
                "file_logging": self.enable_file_logging,
            },
        )


class InterceptHandler(logging.Handler):
    """Redirect standard library logging to Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame: FrameType | None = logging.currentframe()
        depth = 2

        while frame is not None:
            code_filename = frame.f_code.co_filename
            if code_filename == logging.__file__ or code_filename == __file__:
                frame = frame.f_back
                depth += 1
            else:
                break

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())
