"""
Library service for managing photo library data and organization.

This service provides the core functionality for loading, indexing, and organizing
photos into various view modes (All Photos, Days, Months, Years).
"""

from pathlib import Path
from typing import Optional
from datetime import datetime
import logging

from ..models.library_item import LibraryItem, MediaType
from ..models.view_groups import DayGroup, MonthGroup, YearGroup
from .filesystem_scanner import FilesystemScanner
from ..utils.exif_parser import EXIFParser
from ..utils.file_validator import FileValidator

logger = logging.getLogger(__name__)


class LibraryService:
    """
    Core service for library data management.

    Responsibilities:
    - Load and index all photos from filesystem
    - Organize photos into chronological groups
    - Compute quality scores and select highlights
    - Provide efficient querying for different view modes
    """

    def __init__(self, photo_root: Path):
        """
        Initialize library service.

        Args:
            photo_root: Root directory for photo library
        """
        self.photo_root = photo_root
        self._scanner = FilesystemScanner(photo_root)
        self._exif_parser = EXIFParser()

        # Primary data
        self._items: list[LibraryItem] = []

        # Indices for fast lookup
        self._items_by_path: dict[Path, LibraryItem] = {}

        # Default thumbnail size
        self._thumbnail_size = (200, 200)

        logger.info(f"LibraryService initialized for {photo_root}")

    def load_library(self) -> None:
        """
        Load all photos from filesystem, extract EXIF metadata, and create LibraryItem objects.

        This method scans the photo root directory, extracts metadata from each photo,
        and builds the internal index for efficient querying.

        Performance: O(n) where n is the number of photos
        """
        logger.info("Loading library from filesystem...")

        # Clear existing data
        self._items.clear()
        self._items_by_path.clear()

        # Recursively scan for all supported image files
        photo_paths = self._scan_all_photos()

        logger.info(f"Found {len(photo_paths)} photos, extracting metadata...")

        # Process each photo
        for photo_path in photo_paths:
            try:
                item = self._create_library_item(photo_path)
                self._items.append(item)
                self._items_by_path[photo_path] = item
            except Exception as e:
                logger.warning(f"Failed to process {photo_path}: {e}")
                continue

        # Sort by created_date (newest first for default view)
        self._items.sort(key=lambda x: x.created_date, reverse=True)

        logger.info(f"Library loaded: {len(self._items)} items indexed")

    def _scan_all_photos(self) -> list[Path]:
        """
        Recursively scan photo root for all supported image files.

        Returns:
            List of paths to supported image files
        """
        photo_paths = []

        def scan_directory(directory: Path):
            """Recursively scan a directory for photos."""
            try:
                for item in directory.iterdir():
                    if item.is_file() and FileValidator.is_supported_image_format(item):
                        photo_paths.append(item)
                    elif item.is_dir() and not item.name.startswith('.'):
                        # Recursively scan subdirectories
                        scan_directory(item)
            except PermissionError:
                logger.warning(f"Permission denied: {directory}")

        scan_directory(self.photo_root)
        return photo_paths

    def _create_library_item(self, photo_path: Path) -> LibraryItem:
        """
        Create a LibraryItem from a photo file path.

        Args:
            photo_path: Path to photo file

        Returns:
            LibraryItem with extracted metadata
        """
        # Determine media type
        media_type = MediaType.VIDEO if photo_path.suffix.lower() in {'.mp4', '.mov', '.avi', '.mkv'} else MediaType.PHOTO

        # Extract EXIF metadata
        exif_data = {}
        created_date = None
        iso = None
        shutter_speed = None
        aperture = None
        focal_length = None
        exposure_comp = None
        flash_fired = None

        try:
            # Try to extract creation date from EXIF
            created_date = self._exif_parser.extract_date(photo_path)

            # TODO: Extract additional EXIF fields (iso, shutter_speed, etc.)
            # This will be expanded when PhotoQualityRanker is implemented in Phase 4
        except Exception as e:
            logger.debug(f"EXIF extraction failed for {photo_path}: {e}")

        # Fallback to file modification time if no EXIF date
        if created_date is None:
            created_date = datetime.fromtimestamp(photo_path.stat().st_mtime)

        # File modification time for cache invalidation
        modified_date = datetime.fromtimestamp(photo_path.stat().st_mtime)

        # Create LibraryItem
        return LibraryItem(
            path=photo_path,
            media_type=media_type,
            created_date=created_date,
            modified_date=modified_date,
            thumbnail_path=None,  # Will be generated on demand
            thumbnail_size=self._thumbnail_size,
            exif_data=exif_data,
            iso=iso,
            shutter_speed=shutter_speed,
            aperture=aperture,
            focal_length=focal_length,
            exposure_comp=exposure_comp,
            flash_fired=flash_fired,
            quality_score=None,  # Will be computed in Phase 4 (US2)
            duration=None,  # TODO: Extract video duration if media_type is VIDEO
            resolution=None  # TODO: Extract resolution if media_type is VIDEO
        )

    def get_all_items(self, offset: int = 0, limit: int = 200) -> list[LibraryItem]:
        """
        Get all library items in chronological order.

        Args:
            offset: Starting index (for pagination/lazy loading)
            limit: Maximum number of items to return

        Returns:
            List of library items (chronological, most recent first)

        Performance: O(1) with offset/limit (indexed access)
        """
        return self._items[offset:offset + limit]

    def get_total_count(self) -> int:
        """
        Get total number of items in library.

        Returns:
            Total count of photos + videos

        Performance: O(1)
        """
        return len(self._items)

    def get_days(self, year: Optional[int] = None, month: Optional[int] = None) -> list[DayGroup]:
        """
        Get day groups, optionally filtered by year/month.

        Args:
            year: Filter by year (None = all years)
            month: Filter by month (None = all months, requires year if specified)

        Returns:
            List of day groups (reverse chronological)

        Performance: O(1) lookup via index, O(n) for group construction
        """
        # Implementation in Phase 4 (User Story 2)
        raise NotImplementedError("get_days() will be implemented in Phase 4 (US2)")

    def get_months(self, year: Optional[int] = None) -> list[MonthGroup]:
        """
        Get month groups, optionally filtered by year.

        Args:
            year: Filter by year (None = all years)

        Returns:
            List of month groups (reverse chronological)

        Performance: O(1) lookup via index, O(n) for event clustering
        """
        # Implementation in Phase 5 (User Story 3)
        raise NotImplementedError("get_months() will be implemented in Phase 5 (US3)")

    def get_years(self) -> list[YearGroup]:
        """
        Get year groups with highlights.

        Returns:
            List of year groups (reverse chronological)

        Performance: O(n*log(n)) for highlight selection (sort by quality)
        """
        # Implementation in Phase 6 (User Story 4)
        raise NotImplementedError("get_years() will be implemented in Phase 6 (US4)")

    def refresh(self) -> None:
        """
        Refresh library data from filesystem.

        Triggered by FilesystemWatcher when new files detected.
        Re-indexes photos, recomputes groups and scores.

        Performance: O(n) for full re-index
        """
        # Implementation in Phase 7 (Integration & Polish)
        raise NotImplementedError("refresh() will be implemented in Phase 7")

    def get_item_by_path(self, path: Path) -> Optional[LibraryItem]:
        """
        Get a single library item by file path.

        Args:
            path: Absolute path to media file

        Returns:
            Library item or None if not found

        Performance: O(1) via path index
        """
        return self._items_by_path.get(path)
