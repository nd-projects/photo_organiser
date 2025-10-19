"""
Library item model representing a photo or video in the library.

This module defines the LibraryItem dataclass which represents a single media item
with all necessary metadata for display, organization, and quality ranking.
"""

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from enum import Enum


class MediaType(Enum):
    """Type of media item."""
    PHOTO = "photo"
    VIDEO = "video"


@dataclass
class LibraryItem:
    """A media item in the library with display and organization metadata."""

    # Identity
    path: Path                      # Absolute path to source file
    media_type: MediaType           # PHOTO or VIDEO

    # Timestamps (for chronological organization)
    created_date: datetime          # From EXIF DateTimeOriginal, fallback to file mtime
    modified_date: datetime         # File modification time (for cache invalidation)

    # Thumbnail reference
    thumbnail_path: Path | None     # Path to cached thumbnail (None if not yet generated)
    thumbnail_size: tuple[int, int] # Size of thumbnail (width, height)

    # EXIF metadata (for quality ranking and display)
    exif_data: dict                 # Raw EXIF dict from exifread
    iso: int | None = None          # ISO sensitivity (e.g., 100, 400, 3200)
    shutter_speed: float | None = None  # Shutter speed in seconds (e.g., 1/500 = 0.002)
    aperture: float | None = None   # F-stop (e.g., 2.8, 5.6, 11.0)
    focal_length: int | None = None # Focal length in mm (e.g., 50, 200)
    exposure_comp: float | None = None  # Exposure compensation in stops (e.g., -0.5, +1.0)
    flash_fired: bool | None = None # Flash used (True/False/None if unknown)

    # Quality scoring (computed from EXIF)
    quality_score: float | None = None  # 0-100 score, None if EXIF missing

    # Video-specific metadata
    duration: float | None = None   # Video duration in seconds (None for photos)
    resolution: tuple[int, int] | None = None  # Video resolution (width, height), None for photos

    def __post_init__(self):
        """Validation after initialization."""
        assert self.path.exists(), f"Source file does not exist: {self.path}"
        assert self.media_type in MediaType, f"Invalid media type: {self.media_type}"
        if self.quality_score is not None:
            assert 0 <= self.quality_score <= 100, f"Quality score out of range: {self.quality_score}"

    @property
    def display_date(self) -> str:
        """Human-readable date for UI display."""
        return self.created_date.strftime("%B %d, %Y %I:%M %p")

    @property
    def needs_thumbnail(self) -> bool:
        """Check if thumbnail needs to be generated or regenerated."""
        if self.thumbnail_path is None:
            return True  # Never generated
        if not self.thumbnail_path.exists():
            return True  # Cached thumbnail deleted
        # Check if source file modified after thumbnail created
        cache_mtime = self.thumbnail_path.stat().st_mtime
        source_mtime = self.modified_date.timestamp()
        return source_mtime > cache_mtime  # Source newer than cache

    @property
    def is_best_shot(self) -> bool:
        """Determine if this is a candidate for 'best shot' highlighting."""
        if self.quality_score is None:
            return False  # Missing EXIF, can't rank
        return self.quality_score >= 70  # Top 30% threshold
