from pathlib import Path

import pytest

from hospitopt_core.config.settings import BaseAppConfig


def test_base_app_config_from_yaml_resolves_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test that BaseAppConfig can load from YAML and resolve ENV() placeholders."""
    env_values = {
        "DB_HOST": "localhost.test",
        "DB_PORT": "5433",
        "DB_NAME": "hospitopt_test",
        "DB_USER": "hospitopt_user",
        "DB_PASS": "super-secret",  # nosec B105 - test fixture value
    }
    for key, value in env_values.items():
        monkeypatch.setenv(key, value)

    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text(
        """db_connection:
  host: ENV("DB_HOST")
  port: ENV("DB_PORT")
  database: ENV("DB_NAME")
  user: ENV(DB_USER)
  password: ENV('DB_PASS')
"""
    )

    config = BaseAppConfig.from_yaml(yaml_path, load_env=False)

    assert config.db_connection.host == env_values["DB_HOST"]
    assert config.db_connection.port == int(env_values["DB_PORT"])
    assert config.db_connection.database == env_values["DB_NAME"]
    assert config.db_connection.user == env_values["DB_USER"]
    assert config.db_connection.password.get_secret_value() == env_values["DB_PASS"]


def test_base_app_config_from_yaml_missing_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test that BaseAppConfig raises error when ENV() references missing environment variable."""
    monkeypatch.delenv("MISSING_ENV", raising=False)
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text(
        """db_connection:
  host: localhost
  port: 5432
  database: hospitopt
  user: user
  password: ENV(MISSING_ENV)
"""
    )

    with pytest.raises(Exception, match="MISSING_ENV"):
        BaseAppConfig.from_yaml(yaml_path, load_env=False)


def test_base_app_config_from_yaml_file_not_found(tmp_path: Path) -> None:
    """Test that BaseAppConfig raises FileNotFoundError when config file doesn't exist."""
    nonexistent_path = tmp_path / "nonexistent.yaml"

    with pytest.raises(FileNotFoundError, match=f"Config file not found: {nonexistent_path}"):
        BaseAppConfig.from_yaml(nonexistent_path)
