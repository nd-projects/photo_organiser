"""
API Contracts for Library View Feature

This module defines the service interfaces (contracts) for the Library view feature.
These contracts specify the public API that UI components will use to access library data.

Status: Design Phase - Interface definitions for implementation
Date: 2025-10-19
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timedelta
from enum import Enum


# ============================================================================
# Data Transfer Objects (DTOs)
# ============================================================================

class MediaType(Enum):
    """Type of media item."""
    PHOTO = "photo"
    VIDEO = "video"


class ViewMode(Enum):
    """Library view display mode."""
    ALL_PHOTOS = "all_photos"
    DAYS = "days"
    MONTHS = "months"
    YEARS = "years"


@dataclass
class LibraryItemDTO:
    """
    Data transfer object for a library media item.
    Lightweight representation for UI display.
    """
    path: Path
    media_type: MediaType
    created_date: datetime
    thumbnail_path: Path | None
    quality_score: float | None
    duration: float | None  # For videos


@dataclass
class DayGroupDTO:
    """Data transfer object for a day group."""
    date: datetime.date
    items: list[LibraryItemDTO]
    best_shots: list[LibraryItemDTO]
    photo_count: int
    video_count: int


@dataclass
class MonthGroupDTO:
    """Data transfer object for a month group."""
    year: int
    month: int
    items: list[LibraryItemDTO]
    events: list['EventClusterDTO']
    photo_count: int
    video_count: int
    day_count: int


@dataclass
class YearGroupDTO:
    """Data transfer object for a year group."""
    year: int
    items: list[LibraryItemDTO]
    highlights: list[LibraryItemDTO]
    photo_count: int
    video_count: int
    month_count: int


@dataclass
class EventClusterDTO:
    """Data transfer object for an event cluster."""
    items: list[LibraryItemDTO]
    start_time: datetime
    end_time: datetime
    photo_count: int
    video_count: int


# ============================================================================
# Service Interfaces
# ============================================================================

class ILibraryService(ABC):
    """
    Core service interface for library data management.

    Responsibilities:
    - Load and index all photos from filesystem
    - Organize photos into chronological groups
    - Compute quality scores and select highlights
    - Provide efficient querying for different view modes
    """

    @abstractmethod
    def get_all_items(self, offset: int = 0, limit: int = 200) -> list[LibraryItemDTO]:
        """
        Get all library items in chronological order.

        Args:
            offset: Starting index (for pagination/lazy loading)
            limit: Maximum number of items to return

        Returns:
            List of library items (chronological, most recent first)

        Performance: O(1) with offset/limit (indexed access)
        """
        pass

    @abstractmethod
    def get_total_count(self) -> int:
        """
        Get total number of items in library.

        Returns:
            Total count of photos + videos

        Performance: O(1)
        """
        pass

    @abstractmethod
    def get_days(self, year: int | None = None, month: int | None = None) -> list[DayGroupDTO]:
        """
        Get day groups, optionally filtered by year/month.

        Args:
            year: Filter by year (None = all years)
            month: Filter by month (None = all months, requires year if specified)

        Returns:
            List of day groups (reverse chronological)

        Performance: O(1) lookup via index, O(n) for group construction
        """
        pass

    @abstractmethod
    def get_months(self, year: int | None = None) -> list[MonthGroupDTO]:
        """
        Get month groups, optionally filtered by year.

        Args:
            year: Filter by year (None = all years)

        Returns:
            List of month groups (reverse chronological)

        Performance: O(1) lookup via index, O(n) for event clustering
        """
        pass

    @abstractmethod
    def get_years(self) -> list[YearGroupDTO]:
        """
        Get year groups with highlights.

        Returns:
            List of year groups (reverse chronological)

        Performance: O(n*log(n)) for highlight selection (sort by quality)
        """
        pass

    @abstractmethod
    def refresh(self) -> None:
        """
        Refresh library data from filesystem.

        Triggered by FilesystemWatcher when new files detected.
        Re-indexes photos, recomputes groups and scores.

        Performance: O(n) for full re-index
        """
        pass

    @abstractmethod
    def get_item_by_path(self, path: Path) -> LibraryItemDTO | None:
        """
        Get a single library item by file path.

        Args:
            path: Absolute path to media file

        Returns:
            Library item or None if not found

        Performance: O(1) via path index
        """
        pass


class IPhotoQualityRanker(ABC):
    """
    Service interface for photo quality assessment.

    Responsibilities:
    - Extract EXIF metadata for quality metrics
    - Compute quality scores (0-100)
    - Identify best shots for highlighting
    """

    @abstractmethod
    def calculate_score(self, exif_data: dict) -> float:
        """
        Calculate quality score from EXIF metadata.

        Args:
            exif_data: EXIF dictionary from exifread

        Returns:
            Quality score 0-100 (higher = better)
            50.0 if EXIF data is missing/incomplete

        Scoring components:
        - ISO sensitivity (40%): Lower ISO = better
        - Camera shake risk (30%): Based on reciprocal rule
        - Aperture (15%): Mid-range (f/5.6-f/11) optimal
        - Exposure compensation (10%): Small adjustments preferred
        - Flash usage (5%): Preference for natural light

        Performance: O(1) - simple calculation
        """
        pass

    @abstractmethod
    def select_best_shots(self, items: list[LibraryItemDTO], max_count: int) -> list[LibraryItemDTO]:
        """
        Select best shots from a collection.

        Args:
            items: Collection of library items
            max_count: Maximum number of best shots to return

        Returns:
            Top-scoring items (sorted by quality descending)

        Performance: O(n*log(n)) for sorting
        """
        pass

    @abstractmethod
    def select_highlights_with_variety(
        self,
        items: list[LibraryItemDTO],
        target_count: int,
        time_span: timedelta
    ) -> list[LibraryItemDTO]:
        """
        Select highlights balancing quality with temporal variety.

        Used for Years view to ensure highlights spread across the year,
        not just clustered in a few high-quality events.

        Args:
            items: Collection of library items (must span time_span)
            target_count: Desired number of highlights (20-50)
            time_span: Total time period (e.g., 1 year)

        Returns:
            Selected highlights (quality + variety)

        Performance: O(n*log(n)) for sorting + partitioning
        """
        pass


class IEventClusterer(ABC):
    """
    Service interface for time-based event detection.

    Responsibilities:
    - Group photos into events based on time gaps
    - Handle different gap thresholds for Days/Months/Years views
    """

    @abstractmethod
    def cluster_by_time_gaps(
        self,
        items: list[LibraryItemDTO],
        gap_threshold: timedelta
    ) -> list[EventClusterDTO]:
        """
        Group items into events using gap-based clustering.

        Algorithm: O(n) single-pass through sorted items.
        Start new event when time gap exceeds threshold.

        Args:
            items: Library items (must be sorted chronologically)
            gap_threshold: Maximum time gap within an event
                - Days view: 1.5 hours
                - Months view: 3 hours
                - Years view: 1 day

        Returns:
            List of event clusters (chronological)

        Performance: O(n) - single pass
        """
        pass

    @abstractmethod
    def cluster_by_date_boundaries(
        self,
        items: list[LibraryItemDTO],
        gap_threshold: timedelta,
        force_day_boundaries: bool = False
    ) -> list[EventClusterDTO]:
        """
        Cluster with optional day boundary enforcement.

        Args:
            items: Library items (sorted chronologically)
            gap_threshold: Maximum time gap within an event
            force_day_boundaries: If True, never span midnight

        Returns:
            List of event clusters

        Performance: O(n) - single pass with boundary checks
        """
        pass


class IThumbnailLoader(ABC):
    """
    Service interface for asynchronous thumbnail loading.

    Responsibilities:
    - Queue thumbnail generation/loading tasks
    - Manage background worker threads
    - Emit signals when thumbnails ready
    - Handle errors gracefully
    """

    @abstractmethod
    def queue_thumbnail(
        self,
        source_path: Path,
        thumbnail_size: tuple[int, int],
        priority: int = 0
    ) -> None:
        """
        Queue a thumbnail for asynchronous generation/loading.

        Args:
            source_path: Path to source media file
            thumbnail_size: Desired thumbnail size (width, height)
            priority: 0 = high (visible items), 1 = low (pre-cache buffer)

        Behavior:
        - Checks cache first (with mtime validation)
        - If cached and valid, emits thumbnail_ready immediately
        - If not cached, queues generation task for worker thread
        - Emits thumbnail_ready signal when complete
        - Emits thumbnail_failed signal on error

        Performance: O(1) for queue operation
        """
        pass

    @abstractmethod
    def queue_batch(
        self,
        requests: list[tuple[Path, tuple[int, int], int]]
    ) -> None:
        """
        Queue multiple thumbnails (for bulk loading).

        Args:
            requests: List of (source_path, thumbnail_size, priority) tuples

        Performance: O(n) for n requests
        """
        pass

    @abstractmethod
    def clear_queue(self) -> None:
        """
        Clear pending thumbnail tasks.

        Used when view changes to cancel obsolete requests.

        Performance: O(1)
        """
        pass

    @abstractmethod
    def cancel_low_priority(self) -> None:
        """
        Cancel low-priority tasks (pre-cache buffer).

        Used when user scrolls quickly to prioritize visible items.

        Performance: O(n) for n queued tasks
        """
        pass


class ILibraryDataProvider(ABC):
    """
    Unified interface for view-specific data providers.

    Each view mode (All Photos, Days, Months, Years) implements this
    interface to provide data in a consistent format for the UI.
    """

    @abstractmethod
    def get_item_count(self) -> int:
        """
        Get total number of items in this view.

        Returns:
            Total item count (for virtual scrolling)
        """
        pass

    @abstractmethod
    def get_items(self, start: int, end: int) -> list[LibraryItemDTO]:
        """
        Get items in range [start, end) for display.

        Args:
            start: Starting index (inclusive)
            end: Ending index (exclusive)

        Returns:
            List of items in range

        Performance: O(end - start)
        """
        pass

    @abstractmethod
    def refresh_data(self) -> None:
        """
        Refresh data from library service.

        Called when filesystem changes detected.
        """
        pass


# ============================================================================
# PyQt6 Signals (for UI integration)
# ============================================================================

from PyQt6.QtCore import QObject, pyqtSignal


class ThumbnailLoaderSignals(QObject):
    """
    Qt signals emitted by thumbnail loader.

    UI components connect to these signals to update display.
    """

    # Emitted when thumbnail successfully loaded/generated
    # Parameters: (index: int, thumbnail_path: Path)
    thumbnail_ready = pyqtSignal(int, Path)

    # Emitted when thumbnail loading/generation failed
    # Parameters: (index: int, error_message: str)
    thumbnail_failed = pyqtSignal(int, str)

    # Emitted when batch loading starts
    # Parameters: (total_count: int)
    batch_started = pyqtSignal(int)

    # Emitted periodically during batch loading
    # Parameters: (completed_count: int, total_count: int)
    batch_progress = pyqtSignal(int, int)

    # Emitted when batch loading completes
    batch_completed = pyqtSignal()


class LibraryServiceSignals(QObject):
    """
    Qt signals emitted by library service.

    UI components connect to these signals to refresh views.
    """

    # Emitted when library data refreshed (new files detected)
    # Parameters: (added_count: int, removed_count: int)
    library_refreshed = pyqtSignal(int, int)

    # Emitted when indexing starts (for progress UI)
    # Parameters: (total_files: int)
    indexing_started = pyqtSignal(int)

    # Emitted periodically during indexing
    # Parameters: (processed_count: int, total_count: int)
    indexing_progress = pyqtSignal(int, int)

    # Emitted when indexing completes
    indexing_completed = pyqtSignal()


# ============================================================================
# Error Types
# ============================================================================

class LibraryError(Exception):
    """Base exception for library service errors."""
    pass


class ThumbnailGenerationError(LibraryError):
    """Thumbnail generation failed."""
    pass


class InvalidMediaFileError(LibraryError):
    """Media file is corrupted or unsupported format."""
    pass


class EXIFExtractionError(LibraryError):
    """EXIF metadata extraction failed."""
    pass


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class LibraryConfig:
    """Configuration for library service."""

    # Thumbnail settings
    thumbnail_size: tuple[int, int] = (200, 200)
    thumbnail_quality: int = 85

    # Performance settings
    batch_size: int = 200  # Items per lazy load batch
    worker_thread_count: int = 8  # Thumbnail generation workers (default: CPU cores)
    cache_max_items: int = 500  # LRU cache size (QPixmap thumbnails)

    # Event clustering settings
    days_gap_threshold: timedelta = timedelta(hours=1.5)
    months_gap_threshold: timedelta = timedelta(hours=3)
    years_gap_threshold: timedelta = timedelta(days=1)

    # Quality scoring settings
    best_shots_per_day: int = 5
    highlights_per_year_min: int = 20
    highlights_per_year_max: int = 50
    best_shot_min_score: float = 70.0  # Threshold for highlighting

    # View settings
    reverse_chronological: bool = True  # Newest first


# ============================================================================
# Usage Example (Documentation)
# ============================================================================

"""
Usage Example:

from contracts.library_view_api import (
    ILibraryService, IPhotoQualityRanker, IEventClusterer, IThumbnailLoader,
    LibraryConfig, ViewMode
)

# Initialize services (implementations in src/services/)
config = LibraryConfig()
library_service: ILibraryService = LibraryServiceImpl(config)
quality_ranker: IPhotoQualityRanker = PhotoQualityRankerImpl()
event_clusterer: IEventClusterer = EventClustererImpl()
thumbnail_loader: IThumbnailLoader = ThumbnailLoaderImpl(config)

# All Photos view
all_items = library_service.get_all_items(offset=0, limit=200)
for item in all_items:
    thumbnail_loader.queue_thumbnail(item.path, config.thumbnail_size, priority=0)

# Days view
days = library_service.get_days(year=2025, month=10)
for day in days:
    print(f"{day.date}: {len(day.best_shots)} best shots")

# Months view with events
months = library_service.get_months(year=2025)
for month in months:
    for event in month.events:
        print(f"Event: {event.start_time} - {event.end_time}, {len(event.items)} photos")

# Years view with highlights
years = library_service.get_years()
for year in years:
    print(f"{year.year}: {len(year.highlights)} highlights")

# Refresh on filesystem changes
library_service.refresh()
"""
