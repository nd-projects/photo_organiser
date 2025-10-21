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
from .photo_quality import PhotoQualityRanker
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
        self._quality_ranker = PhotoQualityRanker()

        # Primary data
        self._items: list[LibraryItem] = []

        # Indices for fast lookup
        self._items_by_path: dict[Path, LibraryItem] = {}

        # Default thumbnail size
        self._thumbnail_size = (200, 200)

        logger.info(f"LibraryService initialized for {photo_root}")

    def load_library(self, progress_callback=None) -> None:
        """
        Load all photos from filesystem, extract EXIF metadata, and create LibraryItem objects.

        This method scans the photo root directory, extracts metadata from each photo,
        and builds the internal index for efficient querying.

        Args:
            progress_callback: Optional callback function(current, total, message) for progress updates

        Performance: O(n) where n is the number of photos
        """
        logger.info("Loading library from filesystem...")

        # Clear existing data
        self._items.clear()
        self._items_by_path.clear()

        # Recursively scan for all supported image files
        photo_paths = self._scan_all_photos()

        total = len(photo_paths)
        logger.info(f"Found {total} photos, extracting metadata...")

        # Report initial progress
        if progress_callback:
            progress_callback(0, total, "Starting metadata extraction...")

        # Process each photo
        for idx, photo_path in enumerate(photo_paths):
            try:
                item = self._create_library_item(photo_path)
                self._items.append(item)
                self._items_by_path[photo_path] = item

                # Report progress every 10 photos
                if progress_callback and (idx + 1) % 10 == 0:
                    progress_callback(idx + 1, total, f"Processing photo {idx + 1}/{total}...")

            except Exception as e:
                logger.warning(f"Failed to process {photo_path}: {e}")
                continue

        # Final progress update
        if progress_callback:
            progress_callback(total, total, "Sorting photos...")

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
            # Extract full EXIF data
            exif_data = self._exif_parser.extract_exif(photo_path)

            # Extract creation date from EXIF
            created_date = self._exif_parser.extract_date(photo_path)

            # Extract specific EXIF fields for quality scoring
            if exif_data:
                iso = self._extract_exif_int(exif_data, 'EXIF ISOSpeedRatings')
                shutter_speed = self._extract_exif_float(exif_data, 'EXIF ExposureTime')
                aperture = self._extract_exif_float(exif_data, 'EXIF FNumber')
                focal_length = self._extract_exif_int(exif_data, 'EXIF FocalLength')
                exposure_comp = self._extract_exif_float(exif_data, 'EXIF ExposureBiasValue')
                flash_fired = self._extract_flash_status(exif_data)
        except Exception as e:
            logger.debug(f"EXIF extraction failed for {photo_path}: {e}")

        # Fallback to file modification time if no EXIF date
        if created_date is None:
            created_date = datetime.fromtimestamp(photo_path.stat().st_mtime)

        # File modification time for cache invalidation
        modified_date = datetime.fromtimestamp(photo_path.stat().st_mtime)

        # Compute quality score for photos (Phase 4 - US2)
        quality_score = None
        if media_type == MediaType.PHOTO and exif_data:
            try:
                quality_score = self._quality_ranker.calculate_score(exif_data)
            except Exception as e:
                logger.debug(f"Quality scoring failed for {photo_path}: {e}")

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
            quality_score=quality_score,
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

        Performance: O(n) for group construction and quality scoring
        """
        # Filter items by year/month if specified
        filtered_items = self._items
        if year is not None:
            filtered_items = [item for item in filtered_items if item.created_date.year == year]
        if month is not None and year is not None:
            filtered_items = [item for item in filtered_items if item.created_date.month == month]

        # Group items by date
        date_groups = self._group_items_by_date(filtered_items)

        # Create DayGroup objects
        day_groups = []
        for date in sorted(date_groups.keys(), reverse=True):  # Reverse chronological
            items = date_groups[date]

            # Sort items within day chronologically
            items.sort(key=lambda x: x.created_date)

            # Select best shots using quality ranker
            best_shots = self._quality_ranker.select_best_shots(items, max_count=5)

            # Count photos and videos
            photo_count = sum(1 for item in items if item.media_type == MediaType.PHOTO)
            video_count = sum(1 for item in items if item.media_type == MediaType.VIDEO)

            # Create DayGroup
            day_group = DayGroup(
                date=date,
                items=items,
                best_shots=best_shots,
                photo_count=photo_count,
                video_count=video_count,
                events=[]  # Events will be populated in Phase 5 (US3)
            )

            day_groups.append(day_group)

        return day_groups

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

    # ========================================================================
    # Helper Methods for EXIF Extraction
    # ========================================================================

    def _extract_exif_int(self, exif_data: dict, key: str) -> Optional[int]:
        """
        Extract integer value from EXIF data.

        Args:
            exif_data: EXIF dictionary
            key: EXIF key to extract

        Returns:
            Integer value or None if not found/invalid
        """
        try:
            if key in exif_data:
                value = exif_data[key]
                # Handle fraction format
                if hasattr(value, 'num') and hasattr(value, 'den'):
                    return int(value.num / value.den)
                return int(str(value))
        except (ValueError, AttributeError, ZeroDivisionError):
            pass
        return None

    def _extract_exif_float(self, exif_data: dict, key: str) -> Optional[float]:
        """
        Extract float value from EXIF data.

        Args:
            exif_data: EXIF dictionary
            key: EXIF key to extract

        Returns:
            Float value or None if not found/invalid
        """
        try:
            if key in exif_data:
                value = exif_data[key]
                # Handle fraction format
                if hasattr(value, 'num') and hasattr(value, 'den'):
                    return value.num / value.den
                # Handle string format
                val_str = str(value)
                if '/' in val_str:
                    num, den = val_str.split('/')
                    return float(num) / float(den)
                return float(val_str)
        except (ValueError, AttributeError, ZeroDivisionError):
            pass
        return None

    def _extract_flash_status(self, exif_data: dict) -> Optional[bool]:
        """
        Extract flash fired status from EXIF data.

        Args:
            exif_data: EXIF dictionary

        Returns:
            True if flash fired, False if not, None if unknown
        """
        try:
            if 'EXIF Flash' in exif_data:
                value = int(str(exif_data['EXIF Flash']))
                # Flash fired if bit 0 is set
                return (value & 0x01) == 1
        except (ValueError, AttributeError):
            pass
        return None

    # ========================================================================
    # Helper Methods for Day/Month/Year Grouping
    # ========================================================================

    def _group_items_by_date(self, items: list[LibraryItem]) -> dict[datetime.date, list[LibraryItem]]:
        """
        Group items by calendar date.

        Args:
            items: List of LibraryItem objects

        Returns:
            Dictionary mapping date to list of items from that day

        Performance: O(n) single pass
        """
        groups = {}
        for item in items:
            date = item.created_date.date()
            if date not in groups:
                groups[date] = []
            groups[date].append(item)
        return groups
