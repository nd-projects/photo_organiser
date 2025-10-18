"""Application state management with JSON persistence.

This module manages the central application state including photo directory,
albums, and custom album ordering persisted to a JSON file.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal


@dataclass
class AppState:
    """Central application state manager.

    Attributes:
        photo_dir: Root directory containing photo albums
        state_file: Path to JSON state file (default: data/app_state.json)
        thumbnail_cache_dir: Directory for cached thumbnails
        albums: Currently loaded albums
        current_view: Current view state
    """

    photo_dir: Path
    state_file: Path = Path("data/app_state.json")
    thumbnail_cache_dir: Path = Path("data/thumbnails")
    albums: list = field(default_factory=list)
    current_view: Literal["albums", "album_detail", "lightbox"] = "albums"

    def __post_init__(self):
        """Validate paths after initialization."""
        # Ensure photo_dir is a Path object
        if not isinstance(self.photo_dir, Path):
            self.photo_dir = Path(self.photo_dir)
        if not isinstance(self.state_file, Path):
            self.state_file = Path(self.state_file)
        if not isinstance(self.thumbnail_cache_dir, Path):
            self.thumbnail_cache_dir = Path(self.thumbnail_cache_dir)

        # Validate photo directory exists and is readable
        if not self.photo_dir.exists():
            raise ValueError(f"Photo directory does not exist: {self.photo_dir}")
        if not self.photo_dir.is_dir():
            raise ValueError(f"Photo directory is not a directory: {self.photo_dir}")

        # Ensure state file parent directory is writable
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Ensure thumbnail cache directory exists and is writable
        self.thumbnail_cache_dir.mkdir(parents=True, exist_ok=True)

    def load_album_order(self) -> list[dict]:
        """Load album order from JSON state file.

        Returns:
            List of album order dictionaries with album_path, sort_index, metadata
            Returns empty list if file doesn't exist or is invalid.
        """
        if not self.state_file.exists():
            return []

        try:
            with open(self.state_file, "r") as f:
                data = json.load(f)
                return data.get("album_order", [])
        except (json.JSONDecodeError, IOError) as e:
            # Log error but don't crash - return empty order
            print(f"Warning: Could not load album order from {self.state_file}: {e}")
            return []

    def load_settings(self) -> dict:
        """Load application settings from JSON state file.

        Returns:
            Dictionary of settings. Returns defaults if file doesn't exist or is invalid.
        """
        defaults = {"hide_empty_albums": True}

        if not self.state_file.exists():
            return defaults

        try:
            with open(self.state_file, "r") as f:
                data = json.load(f)
                return data.get("settings", defaults)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load settings from {self.state_file}: {e}")
            return defaults

    def save_settings(self, settings: dict) -> None:
        """Save application settings to JSON state file.

        Args:
            settings: Dictionary of settings to save

        Raises:
            IOError: If file cannot be written
        """
        # Load existing data
        existing_data = {}
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    existing_data = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass  # Use empty dict if can't load

        # Update settings
        existing_data["settings"] = settings
        if "version" not in existing_data:
            existing_data["version"] = "1.0"

        # Write to file
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(existing_data, f, indent=2)

    def save_album_order(self, album_order: list[dict]) -> None:
        """Save album order to JSON state file.

        Args:
            album_order: List of dicts with album_path, sort_index, metadata

        Raises:
            IOError: If file cannot be written
        """
        # Ensure parent directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Update timestamps for all entries
        for entry in album_order:
            entry["updated_at"] = datetime.now().isoformat()

        # Create state data structure
        state_data = {"version": "1.0", "album_order": album_order}

        # Write to file with pretty formatting
        with open(self.state_file, "w") as f:
            json.dump(state_data, f, indent=2)

    def get_album_order_map(self) -> dict[str, int]:
        """Get a mapping of album path to sort index.

        Returns:
            Dictionary mapping album_path (str) to sort_index (int)
        """
        album_order = self.load_album_order()
        return {entry["album_path"]: entry["sort_index"] for entry in album_order}

    def update_album_order(
        self, album_path: str, sort_index: int, metadata: dict = None
    ) -> None:
        """Update or insert a single album's order.

        Args:
            album_path: Absolute path to album directory
            sort_index: New sort position (0-based)
            metadata: Optional metadata dict
        """
        album_order = self.load_album_order()

        # Find existing entry
        existing_entry = None
        for entry in album_order:
            if entry["album_path"] == album_path:
                existing_entry = entry
                break

        if existing_entry:
            # Update existing
            existing_entry["sort_index"] = sort_index
            if metadata is not None:
                existing_entry["metadata"] = metadata
        else:
            # Insert new entry
            album_order.append(
                {
                    "album_path": album_path,
                    "sort_index": sort_index,
                    "metadata": metadata or {},
                    "updated_at": datetime.now().isoformat(),
                }
            )

        # Save updated order
        self.save_album_order(album_order)

    def remove_album_order(self, album_path: str) -> None:
        """Remove an album from the ordering (e.g., when album is deleted).

        Args:
            album_path: Absolute path to album directory
        """
        album_order = self.load_album_order()
        album_order = [
            entry for entry in album_order if entry["album_path"] != album_path
        ]
        self.save_album_order(album_order)


def load_album_order(state_file: Path) -> list[dict]:
    """Utility function to load album order from JSON file.

    Args:
        state_file: Path to JSON state file

    Returns:
        List of album order dictionaries
    """
    if not state_file.exists():
        return []

    with open(state_file, "r") as f:
        data = json.load(f)
        return data.get("album_order", [])


def save_album_order(state_file: Path, album_order: list[dict]) -> None:
    """Utility function to save album order to JSON file.

    Args:
        state_file: Path to JSON state file
        album_order: List of album order dictionaries
    """
    state_file.parent.mkdir(parents=True, exist_ok=True)

    data = {"version": "1.0", "album_order": album_order}

    with open(state_file, "w") as f:
        json.dump(data, f, indent=2)
