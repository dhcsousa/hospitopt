from pathlib import Path

import pytest

from hospitopt_worker.settings import WorkerConfig


def test_worker_config_from_yaml_resolves_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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

    yaml_path = tmp_path / "worker.yaml"
    yaml_path.write_text(
        """poll_interval_seconds: 5.5
google_maps_api_key: ENV("GMAPS_KEY")
db_connection:
  host: ENV("DB_HOST")
  port: ENV("DB_PORT")
  database: ENV("DB_NAME")
  user: ENV(DB_USER)
  password: ENV('DB_PASS')
ingestion:
  type: db
  host: ENV("DB_HOST")
  port: ENV("DB_PORT")
  database: ENV("DB_NAME")
  user: ENV("DB_USER")
  password: ENV("DB_PASS")
"""
    )

    config = WorkerConfig.from_yaml(yaml_path, load_env=False)

    assert config.ingestion.host == env_values["DB_HOST"]
    assert config.ingestion.port == int(env_values["DB_PORT"])
    assert config.google_maps_api_key.get_secret_value() == env_values["GMAPS_KEY"]
    assert config.db_connection.password.get_secret_value() == env_values["DB_PASS"]


def test_worker_config_from_yaml_missing_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("MISSING_ENV", raising=False)
    yaml_path = tmp_path / "worker.yaml"
    yaml_path.write_text(
        """poll_interval_seconds: 1
google_maps_api_key: ENV(MISSING_ENV)
db_connection:
  host: localhost
  port: 5432
  database: hospitopt
  user: user
  password: ENV(MISSING_ENV)
ingestion:
  type: db
  host: ENV(MISSING_ENV)
  port: 5432
  database: hospitopt
  user: user
  password: env(MISSING_ENV)
"""
    )

    with pytest.raises(Exception, match="MISSING_ENV"):
        WorkerConfig.from_yaml(yaml_path, load_env=False)
