from pathlib import Path

import pytest

from hospitopt_core.config.settings import AppConfig


def test_from_yaml_resolves_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_values = {
        "DB_HOST": "localhost.test",
        "DB_PORT": "5433",
        "DB_NAME": "hospitopt_test",
        "DB_USER": "hospitopt_user",
        "DB_PASS": "super-secret",  # nosec B105 - test fixture value
        "GMAPS_KEY": "gm-secret",
    }
    for key, value in env_values.items():
        monkeypatch.setenv(key, value)

    yaml_path = tmp_path / "app.yaml"
    yaml_path.write_text(
        """ingestion:
  type: db
  host: ENV("DB_HOST")
  port: ENV("DB_PORT")
  database: ENV("DB_NAME")
  user: ENV("DB_USER")
  password: ENV("DB_PASS")
worker:
  poll_interval_seconds: 5.5
  google_maps_api_key: ENV("GMAPS_KEY")
  db_connection:
    host: ENV("DB_HOST")
    port: ENV("DB_PORT")
    database: ENV("DB_NAME")
    user: ENV(DB_USER)
    password: ENV('DB_PASS')
api:
  api_key: ENV("GMAPS_KEY")
"""
    )

    config = AppConfig.from_yaml(yaml_path, load_env=False)

    assert config.ingestion.host == env_values["DB_HOST"]
    assert config.ingestion.port == int(env_values["DB_PORT"])
    assert config.worker.google_maps_api_key.get_secret_value() == env_values["GMAPS_KEY"]
    assert config.worker.db_connection.password.get_secret_value() == env_values["DB_PASS"]


def test_from_yaml_missing_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("MISSING_ENV", raising=False)
    yaml_path = tmp_path / "app.yaml"
    yaml_path.write_text(
        """ingestion:
  type: db
  host: ENV(MISSING_ENV)
  port: 5432
  database: hospitopt
  user: user
  password: env(MISSING_ENV)
worker:
  poll_interval_seconds: 1
  google_maps_api_key: ENV(MISSING_ENV)
  db_connection:
    host: localhost
    port: 5432
    database: hospitopt
    user: user
    password: ENV(MISSING_ENV)
api:
  api_key: ENV(MISSING_ENV)
"""
    )

    with pytest.raises(Exception, match="MISSING_ENV"):
        AppConfig.from_yaml(yaml_path, load_env=False)
