"""Configuration file loader for Photo Album Organizer.

Supports loading configuration from TOML files as an alternative to CLI arguments.
"""

import tomllib
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass

from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class AppConfig:
    """Application configuration.

    Attributes:
        photo_dir: Root directory containing photo albums
        state_file: Path to JSON state file
        cache_dir: Directory for thumbnail cache
        log_level: Logging level
        log_file: Path to log file (None for console only)
    """

    photo_dir: Path
    state_file: Optional[Path] = None
    cache_dir: Optional[Path] = None
    log_level: str = "INFO"
    log_file: Optional[Path] = None

    def __post_init__(self):
        """Validate and normalize paths after initialization."""
        # Convert strings to Path objects
        if isinstance(self.photo_dir, str):
            self.photo_dir = Path(self.photo_dir)
        if isinstance(self.state_file, str):
            self.state_file = Path(self.state_file)
        if isinstance(self.cache_dir, str):
            self.cache_dir = Path(self.cache_dir)
        if isinstance(self.log_file, str):
            self.log_file = Path(self.log_file)

        # Expand user home directory
        self.photo_dir = self.photo_dir.expanduser()
        if self.state_file:
            self.state_file = self.state_file.expanduser()
        if self.cache_dir:
            self.cache_dir = self.cache_dir.expanduser()
        if self.log_file:
            self.log_file = self.log_file.expanduser()

    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate configuration.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Photo directory must exist and be a directory
        if not self.photo_dir.exists():
            return False, f"Photo directory does not exist: {self.photo_dir}"
        if not self.photo_dir.is_dir():
            return False, f"Photo directory path is not a directory: {self.photo_dir}"

        # Log level must be valid
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_levels:
            return (
                False,
                f"Invalid log level: {self.log_level}. Must be one of: {', '.join(valid_levels)}",
            )

        return True, None


class ConfigLoader:
    """Load configuration from TOML file."""

    DEFAULT_CONFIG_PATHS = [
        Path.cwd() / "config.toml",
        Path.home() / ".config" / "photo-organizer" / "config.toml",
        Path("/etc/photo-organizer/config.toml"),
    ]

    @classmethod
    def find_config_file(cls, config_path: Optional[Path] = None) -> Optional[Path]:
        """Find configuration file.

        Args:
            config_path: Explicit config file path (takes precedence)

        Returns:
            Path to config file, or None if not found
        """
        # If explicit path provided, use it
        if config_path:
            if config_path.exists():
                return config_path
            else:
                logger.warning(f"Specified config file does not exist: {config_path}")
                return None

        # Search default locations
        for path in cls.DEFAULT_CONFIG_PATHS:
            if path.exists():
                logger.info(f"Found config file: {path}")
                return path

        logger.debug("No config file found in default locations")
        return None

    @classmethod
    def load_config(cls, config_path: Optional[Path] = None) -> Optional[AppConfig]:
        """Load configuration from TOML file.

        Args:
            config_path: Optional explicit path to config file

        Returns:
            AppConfig object, or None if no config file found

        Raises:
            ValueError: If config file is invalid
        """
        config_file = cls.find_config_file(config_path)

        if not config_file:
            return None

        try:
            with open(config_file, "rb") as f:
                data = tomllib.load(f)

            logger.info(f"Loaded configuration from: {config_file}")

            # Extract configuration values
            return cls._parse_config_data(data, config_file)

        except tomllib.TOMLDecodeError as e:
            raise ValueError(f"Invalid TOML syntax in config file {config_file}: {e}")
        except Exception as e:
            raise ValueError(f"Error loading config file {config_file}: {e}")

    @classmethod
    def _parse_config_data(cls, data: dict[str, Any], source: Path) -> AppConfig:
        """Parse configuration data from TOML.

        Args:
            data: Parsed TOML data
            source: Source config file path (for error messages)

        Returns:
            AppConfig object

        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Photo directory is required
        if "photo_dir" not in data:
            raise ValueError(
                f"Missing required field 'photo_dir' in config file {source}"
            )

        # Build config object
        config = AppConfig(
            photo_dir=Path(data["photo_dir"]),
            state_file=Path(data["state_file"]) if "state_file" in data else None,
            cache_dir=Path(data["cache_dir"]) if "cache_dir" in data else None,
            log_level=data.get("log_level", "INFO"),
            log_file=Path(data["log_file"]) if "log_file" in data else None,
        )

        # Validate configuration
        is_valid, error_msg = config.validate()
        if not is_valid:
            raise ValueError(f"Invalid configuration in {source}: {error_msg}")

        return config

    @classmethod
    def create_example_config(cls, output_path: Path) -> None:
        """Create an example configuration file.

        Args:
            output_path: Path where to write example config
        """
        example = """# Photo Album Organizer Configuration File
#
# This file provides an alternative to command-line arguments.
# CLI arguments take precedence over config file settings.
#
# Config file locations (in order of precedence):
# 1. Specified via --config CLI argument
# 2. ./config.toml (current directory)
# 3. ~/.config/photo-organizer/config.toml
# 4. /etc/photo-organizer/config.toml

# Photo directory (required)
# Root directory containing photo albums
photo_dir = "~/Pictures"

# State file (optional)
# Path to JSON file storing application state (album ordering, etc.)
# Default: data/app_state.json
# state_file = "~/.local/share/photo-organizer/app_state.json"

# Cache directory (optional)
# Directory for thumbnail cache
# Default: data/thumbnails
# cache_dir = "~/.cache/photo-organizer/thumbnails"

# Logging configuration (optional)
# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
# Default: INFO
log_level = "INFO"

# Log file path (optional)
# If not specified, logs go to console only
# log_file = "~/.local/share/photo-organizer/app.log"
"""

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(example)

        logger.info(f"Created example config file: {output_path}")
