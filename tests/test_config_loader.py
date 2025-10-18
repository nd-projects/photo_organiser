"""Tests for configuration file loading.

Tests the config_loader module's ability to load and validate TOML configuration files.
"""

import pytest
import tempfile
import tomllib
from pathlib import Path

from src.utils.config_loader import ConfigLoader, AppConfig


class TestAppConfig:
    """Tests for AppConfig dataclass."""

    def test_path_expansion(self, tmp_path):
        """Test that paths are expanded (e.g., ~ to home directory)."""
        config = AppConfig(
            photo_dir=Path("~/Pictures"),
            state_file=Path("~/data/state.json"),
            log_file=Path("~/logs/app.log")
        )

        # Paths should be expanded
        assert not str(config.photo_dir).startswith("~")
        assert not str(config.state_file).startswith("~")
        assert not str(config.log_file).startswith("~")

    def test_string_to_path_conversion(self):
        """Test that string paths are converted to Path objects."""
        config = AppConfig(
            photo_dir="/tmp/photos",
            state_file="/tmp/state.json"
        )

        assert isinstance(config.photo_dir, Path)
        assert isinstance(config.state_file, Path)

    def test_validation_missing_directory(self):
        """Test validation fails for non-existent directory."""
        config = AppConfig(photo_dir=Path("/nonexistent/path"))

        is_valid, error_msg = config.validate()

        assert not is_valid
        assert "does not exist" in error_msg

    def test_validation_invalid_log_level(self, tmp_path):
        """Test validation fails for invalid log level."""
        config = AppConfig(
            photo_dir=tmp_path,
            log_level="INVALID"
        )

        is_valid, error_msg = config.validate()

        assert not is_valid
        assert "Invalid log level" in error_msg

    def test_validation_success(self, tmp_path):
        """Test validation succeeds for valid config."""
        config = AppConfig(
            photo_dir=tmp_path,
            log_level="DEBUG"
        )

        is_valid, error_msg = config.validate()

        assert is_valid
        assert error_msg is None


class TestConfigLoader:
    """Tests for ConfigLoader class."""

    def test_load_valid_config(self, tmp_path):
        """Test loading a valid TOML config file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(f"""
photo_dir = "{tmp_path}"
log_level = "DEBUG"
        """)

        config = ConfigLoader.load_config(config_file)

        assert config is not None
        assert config.photo_dir == tmp_path
        assert config.log_level == "DEBUG"

    def test_load_config_with_optional_fields(self, tmp_path):
        """Test loading config with all optional fields."""
        config_file = tmp_path / "config.toml"
        state_file = tmp_path / "state.json"
        cache_dir = tmp_path / "cache"
        log_file = tmp_path / "app.log"

        config_file.write_text(f"""
photo_dir = "{tmp_path}"
state_file = "{state_file}"
cache_dir = "{cache_dir}"
log_level = "WARNING"
log_file = "{log_file}"
        """)

        config = ConfigLoader.load_config(config_file)

        assert config is not None
        assert config.photo_dir == tmp_path
        assert config.state_file == state_file
        assert config.cache_dir == cache_dir
        assert config.log_level == "WARNING"
        assert config.log_file == log_file

    def test_load_nonexistent_config(self):
        """Test loading a config file that doesn't exist."""
        config = ConfigLoader.load_config(Path("/nonexistent/config.toml"))

        assert config is None

    def test_load_invalid_toml(self, tmp_path):
        """Test loading an invalid TOML file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("invalid toml syntax [[[")

        with pytest.raises(ValueError, match="Invalid TOML syntax"):
            ConfigLoader.load_config(config_file)

    def test_load_missing_required_field(self, tmp_path):
        """Test loading config without required photo_dir field."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
log_level = "INFO"
        """)

        with pytest.raises(ValueError, match="Missing required field"):
            ConfigLoader.load_config(config_file)

    def test_load_invalid_photo_dir(self, tmp_path):
        """Test loading config with invalid photo_dir."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
photo_dir = "/nonexistent/path"
        """)

        with pytest.raises(ValueError, match="does not exist"):
            ConfigLoader.load_config(config_file)

    def test_find_config_file_explicit(self, tmp_path):
        """Test finding config file with explicit path."""
        config_file = tmp_path / "my_config.toml"
        config_file.write_text("")

        found = ConfigLoader.find_config_file(config_file)

        assert found == config_file

    def test_find_config_file_default_locations(self, tmp_path, monkeypatch):
        """Test finding config file in default locations."""
        # Create config in test directory
        config_file = tmp_path / "config.toml"
        config_file.write_text("")

        # Mock DEFAULT_CONFIG_PATHS to use test directory
        monkeypatch.setattr(
            ConfigLoader,
            "DEFAULT_CONFIG_PATHS",
            [config_file, tmp_path / "other.toml"]
        )

        found = ConfigLoader.find_config_file()

        assert found == config_file

    def test_find_config_file_not_found(self):
        """Test behavior when no config file found."""
        found = ConfigLoader.find_config_file(Path("/nonexistent/config.toml"))

        assert found is None

    def test_create_example_config(self, tmp_path):
        """Test creating an example config file."""
        output_file = tmp_path / "example.toml"

        ConfigLoader.create_example_config(output_file)

        assert output_file.exists()

        # Verify it's valid TOML
        with open(output_file, "rb") as f:
            data = tomllib.load(f)
            assert "photo_dir" in data
            assert data["photo_dir"] == "~/Pictures"
            assert data["log_level"] == "INFO"
