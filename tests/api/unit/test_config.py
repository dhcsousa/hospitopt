from pathlib import Path

import pytest

from hospitopt_api.settings import APIConfig


def test_api_config_from_yaml_resolves_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_values = {
        "DB_HOST": "localhost.test",
        "DB_PORT": "5433",
        "DB_NAME": "hospitopt_test",
        "DB_USER": "hospitopt_user",
        "DB_PASS": "super-secret",  # nosec B105 - test fixture value
        "API_KEY": "api-secret",
    }
    for key, value in env_values.items():
        monkeypatch.setenv(key, value)

    yaml_path = tmp_path / "api.yaml"
    yaml_path.write_text(
        """api_key: ENV("API_KEY")
db_connection:
  host: ENV("DB_HOST")
  port: ENV("DB_PORT")
  database: ENV("DB_NAME")
  user: ENV("DB_USER")
  password: ENV("DB_PASS")
cors:
  allow_origins:
    - http://localhost:3000
  allow_credentials: true
  allow_methods:
    - GET
    - POST
  allow_headers:
    - "*"
"""
    )

    config = APIConfig.from_yaml(yaml_path, load_env=False)

    assert config.api_key.get_secret_value() == env_values["API_KEY"]
    assert config.db_connection.host == env_values["DB_HOST"]
    assert config.db_connection.port == int(env_values["DB_PORT"])
    assert config.db_connection.password.get_secret_value() == env_values["DB_PASS"]
    assert config.cors.allow_credentials is True
    assert len(config.cors.allow_origins) == 1


def test_api_config_from_yaml_missing_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("MISSING_ENV", raising=False)
    yaml_path = tmp_path / "api.yaml"
    yaml_path.write_text(
        """api_key: ENV(MISSING_ENV)
db_connection:
  host: localhost
  port: 5432
  database: hospitopt
  user: user
  password: ENV(MISSING_ENV)
"""
    )

    with pytest.raises(Exception, match="MISSING_ENV"):
        APIConfig.from_yaml(yaml_path, load_env=False)
