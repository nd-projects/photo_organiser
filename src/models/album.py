"""Album model representing a photo collection.

An album corresponds to a filesystem directory containing photos.
Albums are never nested within other albums (flat hierarchy).
"""

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional


@dataclass
class Album:
    """Photo album entity.

    Attributes:
        path: Absolute path to album directory
        name: Display name (directory name or custom name)
        date: Parsed date from folder name or None
        photo_count: Number of photos in album (cached)
        thumbnail_path: Path to preview thumbnail
        photos: Lazy-loaded list of photos
    """

    path: Path
    name: str = ""
    date: Optional[date] = None
    photo_count: int = 0
    thumbnail_path: Optional[Path] = None
    photos: list = field(default_factory=list)

    def __post_init__(self):
        """Initialize derived attributes after dataclass creation."""
        # Ensure path is Path object
        if not isinstance(self.path, Path):
            self.path = Path(self.path)

        # Set name from directory name if not provided
        if not self.name:
            self.name = self.path.name

        # Parse date from directory name if not set
        if self.date is None:
            self.date = self.parse_date_from_name(self.name)

    @staticmethod
    def parse_date_from_name(name: str) -> Optional[date]:
        """Extract date from folder name.

        Supports formats like:
        - 2022-12-08
        - 2022-12-08_Paris
        - 2022-12-08_Paris_City

        Args:
            name: Folder name

        Returns:
            Date object if parsing succeeds, None otherwise
        """
        # Match YYYY-MM-DD at start of name
        match = re.match(r'^(\d{4})-(\d{2})-(\d{2})', name)
        if match:
            year, month, day = map(int, match.groups())
            try:
                return date(year, month, day)
            except ValueError:
                # Invalid date (e.g., 2022-13-45)
                return None
        return None

    @property
    def display_name(self) -> str:
        """Get formatted display name for UI.

        Returns:
            Album name with date if available
        """
        return self.name

    @property
    def date_string(self) -> str:
        """Get formatted date string.

        Returns:
            Formatted date or "Unknown Date"
        """
        if self.date:
            return self.date.strftime('%Y-%m-%d')
        return "Unknown Date"

    @property
    def is_loaded(self) -> bool:
        """Check if photos have been loaded.

        Returns:
            True if photos list is populated
        """
        return len(self.photos) > 0

    def load_photos(self) -> list:
        """Lazy-load photos from directory.

        This method should be implemented by the AlbumManager service.
        Here we just provide the interface.

        Returns:
            List of Photo objects
        """
        # This will be implemented by AlbumManager
        # For now, return the current photos list
        return self.photos

    def generate_thumbnail(self, thumbnail_generator) -> Optional[Path]:
        """Generate preview thumbnail from first photo.

        Args:
            thumbnail_generator: Callable that generates thumbnails

        Returns:
            Path to generated thumbnail or None
        """
        if not self.photos:
            return None

        # Get first photo
        first_photo = self.photos[0]

        # Generate thumbnail using the provided generator
        try:
            thumbnail_path = thumbnail_generator(first_photo.path, size=(200, 200))
            self.thumbnail_path = thumbnail_path
            return thumbnail_path
        except Exception as e:
            print(f"Warning: Could not generate thumbnail for album {self.name}: {e}")
            return None

    def __str__(self) -> str:
        """String representation."""
        return f"Album({self.name}, {self.photo_count} photos, {self.date_string})"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return f"Album(path={self.path}, name={self.name}, date={self.date}, count={self.photo_count})"
