import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context  # type: ignore[attr-defined]
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from core.config.env import Environment
from core.config.settings import AppConfig
from core.db.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

BASE_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

load_dotenv(BASE_DIR / ".env")

# Priority: ENV_VAR > CONFIG_FILE > alembic.ini
database_url = os.getenv("DATABASE_URL")

# If DATABASE_URL is not set, try to construct it from individual components
if not database_url:
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_hostname = os.getenv("DB_HOST")
    db_database_name = os.getenv("DB_NAME")
    db_port = os.getenv("DB_PORT", "5432")
    db_driver = os.getenv("DB_DRIVER", "postgresql+asyncpg")

    if all([db_user, db_password, db_hostname, db_database_name]):
        database_url = f"{db_driver}://{db_user}:{db_password}@{db_hostname}:{db_port}/{db_database_name}"

if not database_url:
    try:
        env = Environment()
        app_config = AppConfig.from_yaml(env.CONFIG_FILE_PATH)
        database_url = app_config.ingestion.connection_string()
    except Exception:
        database_url = database_url

if database_url:
    config.set_main_option("sqlalchemy.url", database_url)
else:
    raise RuntimeError(
        "Missing database configuration. Set DATABASE_URL or CONFIG_FILE_PATH (.env) "
        "to a YAML config containing DB connection details."
    )

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
