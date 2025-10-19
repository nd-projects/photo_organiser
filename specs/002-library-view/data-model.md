# Data Model: Library View

**Feature**: Library View (002-library-view)
**Date**: 2025-10-19
**Status**: Design Phase

## Overview

This document defines the data entities, relationships, and validation rules for the Library view feature. All entities are designed to support 50,000+ photos with bounded memory usage and efficient querying.

---

## Core Entities

### 1. LibraryItem

**Purpose**: Represents a single media item (photo or video) in the library with metadata for display and organization.

**Source**: Extracted from `spec.md` Key Entities (MediaItem)

```python
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from enum import Enum

class MediaType(Enum):
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
    iso: int | None                 # ISO sensitivity (e.g., 100, 400, 3200)
    shutter_speed: float | None     # Shutter speed in seconds (e.g., 1/500 = 0.002)
    aperture: float | None          # F-stop (e.g., 2.8, 5.6, 11.0)
    focal_length: int | None        # Focal length in mm (e.g., 50, 200)
    exposure_comp: float | None     # Exposure compensation in stops (e.g., -0.5, +1.0)
    flash_fired: bool | None        # Flash used (True/False/None if unknown)

    # Quality scoring (computed from EXIF)
    quality_score: float | None     # 0-100 score, None if EXIF missing (see photo_quality.py)

    # Video-specific metadata
    duration: float | None          # Video duration in seconds (None for photos)
    resolution: tuple[int, int] | None  # Video resolution (width, height), None for photos

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
```

**Relationships**:

- Member of zero or more `DayGroup`, `MonthGroup`, `YearGroup` (organized views)
- References `Photo` entity from existing models (may share data, TBD in implementation)

---

### 2. DayGroup

**Purpose**: Groups media items from a single calendar day, with best shots highlighted.

**Source**: Extracted from `spec.md` Key Entities

```python
@dataclass
class DayGroup:
    """Collection of media items from a single calendar day."""

    # Identity
    date: datetime.date             # Calendar date (year, month, day)

    # Items
    items: list[LibraryItem]        # All media from this day (chronological order)
    best_shots: list[LibraryItem]   # Top-quality photos (5-10 items)

    # Statistics
    photo_count: int                # Number of photos
    video_count: int                # Number of videos

    # Events within the day (time-based clustering)
    events: list['EventCluster']    # Sub-groups within the day (optional)

    def __post_init__(self):
        """Validation and derived data."""
        assert len(self.items) > 0, "DayGroup must have at least one item"
        assert all(item.created_date.date() == self.date for item in self.items), \
            "All items must be from the same day"
        assert len(self.best_shots) <= 10, "Too many best shots (max 10)"
        # Ensure items are sorted chronologically
        self.items.sort(key=lambda x: x.created_date)

    @property
    def display_title(self) -> str:
        """Human-readable title for UI display."""
        return self.date.strftime("%A, %B %d, %Y")  # "Monday, October 19, 2025"

    @property
    def total_count(self) -> int:
        """Total media items in this day."""
        return len(self.items)
```

**Relationships**:

- Contains multiple `LibraryItem` entities
- May contain multiple `EventCluster` sub-groups (within-day events)
- Member of a `MonthGroup`

---

### 3. MonthGroup

**Purpose**: Groups media items from a single calendar month, organized by significant events.

**Source**: Extracted from `spec.md` Key Entities

```python
@dataclass
class MonthGroup:
    """Collection of media items from a single calendar month."""

    # Identity
    year: int                       # Year (e.g., 2025)
    month: int                      # Month (1-12)

    # Items
    items: list[LibraryItem]        # All media from this month (chronological order)
    events: list['EventCluster']    # Time-based event clusters

    # Day-level organization
    days: list[DayGroup]            # Days with photos (sparse - only days with content)

    # Statistics
    photo_count: int                # Number of photos
    video_count: int                # Number of videos
    day_count: int                  # Number of days with photos

    def __post_init__(self):
        """Validation and derived data."""
        assert 1 <= self.month <= 12, f"Invalid month: {self.month}"
        assert len(self.items) > 0, "MonthGroup must have at least one item"
        # Ensure items are sorted chronologically
        self.items.sort(key=lambda x: x.created_date)

    @property
    def display_title(self) -> str:
        """Human-readable title for UI display."""
        return datetime(self.year, self.month, 1).strftime("%B %Y")  # "October 2025"

    @property
    def total_count(self) -> int:
        """Total media items in this month."""
        return len(self.items)

    @property
    def date_range(self) -> tuple[datetime.date, datetime.date]:
        """First and last date with photos."""
        return (self.items[0].created_date.date(), self.items[-1].created_date.date())
```

**Relationships**:

- Contains multiple `LibraryItem` entities
- Contains multiple `DayGroup` entities (only days with photos)
- Contains multiple `EventCluster` entities (significant events within month)
- Member of a `YearGroup`

---

### 4. YearGroup

**Purpose**: Groups media items from a single calendar year, with highlights selected for variety and quality.

**Source**: Extracted from `spec.md` Key Entities

```python
@dataclass
class YearGroup:
    """Collection of media items from a single calendar year."""

    # Identity
    year: int                       # Year (e.g., 2025)

    # Items
    items: list[LibraryItem]        # All media from this year (chronological order)
    highlights: list[LibraryItem]   # Best photos (20-50 items, spread across year)

    # Month-level organization
    months: list[MonthGroup]        # Months with photos (sparse - only months with content)

    # Statistics
    photo_count: int                # Number of photos
    video_count: int                # Number of videos
    month_count: int                # Number of months with photos

    def __post_init__(self):
        """Validation and derived data."""
        assert len(self.items) > 0, "YearGroup must have at least one item"
        assert 20 <= len(self.highlights) <= 50, \
            f"Highlights count out of range (20-50): {len(self.highlights)}"
        # Ensure items are sorted chronologically
        self.items.sort(key=lambda x: x.created_date)

    @property
    def display_title(self) -> str:
        """Human-readable title for UI display."""
        return str(self.year)  # "2025"

    @property
    def total_count(self) -> int:
        """Total media items in this year."""
        return len(self.items)

    @property
    def date_range(self) -> tuple[datetime.date, datetime.date]:
        """First and last date with photos."""
        return (self.items[0].created_date.date(), self.items[-1].created_date.date())
```

**Relationships**:

- Contains multiple `LibraryItem` entities
- Contains multiple `MonthGroup` entities (only months with photos)

---

### 5. EventCluster

**Purpose**: Groups media items from a single event/occasion based on time proximity.

**Source**: Derived from `spec.md` FR-010, FR-019 (time-based clustering)

```python
@dataclass
class EventCluster:
    """Collection of media items from a single event (time-based clustering)."""

    # Items
    items: list[LibraryItem]        # All media in this event (chronological order)

    # Time boundaries
    start_time: datetime            # First photo timestamp
    end_time: datetime              # Last photo timestamp

    # Statistics
    photo_count: int                # Number of photos
    video_count: int                # Number of videos

    def __post_init__(self):
        """Validation and derived data."""
        assert len(self.items) > 0, "EventCluster must have at least one item"
        assert self.start_time <= self.end_time, "Invalid time range"
        # Ensure items are sorted chronologically
        self.items.sort(key=lambda x: x.created_date)

    @property
    def duration(self) -> float:
        """Event duration in hours."""
        return (self.end_time - self.start_time).total_seconds() / 3600

    @property
    def display_time_range(self) -> str:
        """Human-readable time range for UI display."""
        if self.start_time.date() == self.end_time.date():
            # Same day: "2:30 PM - 5:45 PM"
            return f"{self.start_time.strftime('%I:%M %p')} - {self.end_time.strftime('%I:%M %p')}"
        else:
            # Multiple days: "Oct 19, 2:30 PM - Oct 20, 5:45 PM"
            return f"{self.start_time.strftime('%b %d, %I:%M %p')} - {self.end_time.strftime('%b %d, %I:%M %p')}"

    @property
    def total_count(self) -> int:
        """Total media items in this event."""
        return len(self.items)
```

**Relationships**:

- Contains multiple `LibraryItem` entities
- Member of a `DayGroup` or `MonthGroup` (depending on context)

---

## View-Specific Models (PyQt6)

### 6. PhotoLibraryModel (QAbstractListModel)

**Purpose**: Qt model for efficiently displaying library items in a virtual scrolling grid.

**Source**: Derived from [research.md](research.md) QAbstractListModel pattern

```python
from PyQt6.QtCore import QAbstractListModel, Qt, QModelIndex, pyqtSignal

class PhotoLibraryModel(QAbstractListModel):
    """Virtual model for library grid display with lazy loading."""

    # Signals
    thumbnailRequested = pyqtSignal(int, Path)  # index, source_path

    def __init__(self, items: list[LibraryItem], batch_size: int = 200):
        super().__init__()
        self._items = items          # Full item list (metadata only)
        self._batch_size = batch_size
        self._loaded_count = min(batch_size, len(items))  # Initially load first batch

    def rowCount(self, parent=QModelIndex()) -> int:
        """Return number of loaded items (not total!)."""
        return self._loaded_count

    def data(self, index: QModelIndex, role: int):
        """Return data for role (Qt calls only for visible items)."""
        if not index.isValid() or index.row() >= self._loaded_count:
            return None

        item = self._items[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            return item.display_date
        elif role == Qt.ItemDataRole.DecorationRole:
            # Thumbnail loading handled by delegate
            return None
        elif role == Qt.ItemDataRole.UserRole:
            # Return full item for delegate access
            return item

        return None

    def canFetchMore(self, parent=QModelIndex()) -> bool:
        """Check if more items can be loaded."""
        return self._loaded_count < len(self._items)

    def fetchMore(self, parent=QModelIndex()):
        """Load next batch (Qt calls automatically when scrolling)."""
        remaining = len(self._items) - self._loaded_count
        items_to_fetch = min(remaining, self._batch_size)

        self.beginInsertRows(QModelIndex(), self._loaded_count,
                            self._loaded_count + items_to_fetch - 1)
        self._loaded_count += items_to_fetch
        self.endInsertRows()
```

**Validation Rules**:

- `items` list must be pre-sorted (chronological or by quality score)
- `batch_size` must be > 0 (default 200 for smooth scrolling)
- Model is read-only (no insertions/deletions after construction)

---

## Derived Data & Computations

### Quality Score Calculation

**Source**: [research-photo-quality-ranking.md](research-photo-quality-ranking.md)

Computed once during `LibraryItem` creation, cached in `quality_score` field:

```python
def calculate_quality_score(item: LibraryItem) -> float:
    """
    Compute 0-100 quality score from EXIF metadata.
    Returns 50.0 if EXIF data is missing (neutral score).
    """
    if not item.exif_data:
        return 50.0  # Neutral score for missing EXIF

    # Component scores (0-100 each)
    iso_score = _score_iso(item.iso)
    shake_score = _score_camera_shake(item.shutter_speed, item.focal_length)
    aperture_score = _score_aperture(item.aperture)
    exposure_score = _score_exposure_comp(item.exposure_comp)
    flash_score = _score_flash(item.flash_fired)

    # Weighted combination
    weighted = (
        iso_score * 0.40 +
        shake_score * 0.30 +
        aperture_score * 0.15 +
        exposure_score * 0.10 +
        flash_score * 0.05
    )

    return max(0.0, min(100.0, weighted))  # Clamp to 0-100
```

### Best Shot Selection

**Days View** (FR-008):

```python
def select_best_shots(day: DayGroup, max_count: int = 5) -> list[LibraryItem]:
    """Select top N photos by quality score for highlighting."""
    photos = [item for item in day.items if item.media_type == MediaType.PHOTO]
    scored = [photo for photo in photos if photo.quality_score is not None]
    scored.sort(key=lambda p: p.quality_score, reverse=True)
    return scored[:max_count]
```

**Years View** (FR-020):

```python
def select_yearly_highlights(year: YearGroup, target_count: int = 30) -> list[LibraryItem]:
    """
    Select 20-50 highlights balancing quality with temporal variety.
    Ensures representation across all months with photos.
    """
    highlights = []
    photos_per_month = target_count // len(year.months)

    for month in year.months:
        # Get top photos from this month
        month_photos = [item for item in month.items if item.media_type == MediaType.PHOTO]
        scored = [p for p in month_photos if p.quality_score is not None]
        scored.sort(key=lambda p: p.quality_score, reverse=True)

        # Take proportional share (minimum 2 per month)
        count = max(2, photos_per_month)
        highlights.extend(scored[:count])

    # Ensure total count in range [20, 50]
    highlights.sort(key=lambda p: p.quality_score, reverse=True)
    return highlights[:50]  # Cap at 50
```

### Event Clustering

**Source**: [research-photo-quality-ranking.md](research-photo-quality-ranking.md)

```python
def cluster_by_time_gaps(items: list[LibraryItem], gap_threshold: timedelta) -> list[EventCluster]:
    """
    Group items into events based on time gaps.
    O(n) single-pass algorithm.
    """
    if not items:
        return []

    items_sorted = sorted(items, key=lambda x: x.created_date)
    clusters = []
    current_cluster_items = [items_sorted[0]]

    for item in items_sorted[1:]:
        gap = item.created_date - current_cluster_items[-1].created_date
        if gap <= gap_threshold:
            current_cluster_items.append(item)  # Same event
        else:
            # Finalize current cluster, start new one
            clusters.append(_create_event_cluster(current_cluster_items))
            current_cluster_items = [item]

    # Add final cluster
    clusters.append(_create_event_cluster(current_cluster_items))
    return clusters

def _create_event_cluster(items: list[LibraryItem]) -> EventCluster:
    """Create EventCluster from items."""
    return EventCluster(
        items=items,
        start_time=items[0].created_date,
        end_time=items[-1].created_date,
        photo_count=sum(1 for i in items if i.media_type == MediaType.PHOTO),
        video_count=sum(1 for i in items if i.media_type == MediaType.VIDEO)
    )
```

**Gap Thresholds**:

- Days view: `timedelta(hours=1.5)` - Multiple sessions per day
- Months view: `timedelta(hours=3)` - Distinct events/occasions
- Years view: `timedelta(days=1)` - Major multi-day events

---

## State Transitions

### LibraryItem Lifecycle

```
[Discovered by FilesystemScanner]
    → [EXIF extracted]
    → [Quality scored]
    → [Added to groups]
    → [Thumbnail generated]
    → [Displayed in grid]
```

**State Changes**:

1. **File Modified** (detected by FilesystemWatcher):
   - `modified_date` updated
   - `needs_thumbnail` returns `True`
   - Thumbnail regenerated asynchronously
   - Quality score recalculated if EXIF changed

2. **File Deleted** (detected by FilesystemWatcher):
   - Item removed from all groups
   - Thumbnail cache entry deleted
   - UI updated to remove item

3. **File Added** (detected by FilesystemWatcher):
   - New `LibraryItem` created
   - Added to appropriate groups
   - Thumbnail queued for generation
   - UI updated to show new item

---

## Memory Budget & Optimization

**Target**: <500MB for 50,000 photos

| Component | Size per Item | Total (50k) | Strategy |
|-----------|---------------|-------------|----------|
| LibraryItem metadata | ~1 KB | 50 MB | Full collection in memory |
| Grouping indices | ~100 bytes | 5 MB | Lightweight references |
| QPixmap thumbnail cache | ~160 KB | 80 MB | LRU cache (500 items max) |
| Qt model overhead | ~100 bytes | 5 MB | Virtual model, lazy loading |
| **Total** | | **~140 MB** | ✅ Well under limit |

**Optimization Strategies**:

1. **Lazy Loading**: Only load metadata initially, thumbnails on-demand
2. **LRU Cache**: Evict oldest thumbnails when cache exceeds 500 items
3. **Virtual Scrolling**: Render only visible items (typically 20-50)
4. **Streaming**: Load groups incrementally (200 items per batch)
5. **Disk Cache**: Thumbnails persisted to disk, loaded as needed

---

## Validation Rules

### LibraryItem

- ✅ `path` must exist on filesystem
- ✅ `created_date` must be <= current time
- ✅ `quality_score` must be in range [0, 100] or None
- ✅ `duration` > 0 if media_type == VIDEO
- ✅ `thumbnail_size` must be > (0, 0)

### DayGroup

- ✅ All items must have `created_date.date() == date`
- ✅ `items` must be sorted chronologically
- ✅ `best_shots` must be subset of `items`
- ✅ `best_shots` count <= 10

### MonthGroup

- ✅ All items must have `created_date.month == month` and `created_date.year == year`
- ✅ `items` must be sorted chronologically
- ✅ `days` must only include days with photos (sparse)
- ✅ `month` must be in range [1, 12]

### YearGroup

- ✅ All items must have `created_date.year == year`
- ✅ `items` must be sorted chronologically
- ✅ `highlights` count must be in range [20, 50]
- ✅ `months` must only include months with photos (sparse)

### EventCluster

- ✅ `items` must be sorted chronologically
- ✅ `start_time` <= `end_time`
- ✅ All items must have timestamps within [start_time, end_time]

---

## Relationships Diagram

```
YearGroup (2025)
    ├── highlights: list[LibraryItem]  (20-50 best photos)
    └── months: list[MonthGroup]  (sparse)
            ├── MonthGroup (October 2025)
            │       ├── items: list[LibraryItem]
            │       ├── events: list[EventCluster]
            │       └── days: list[DayGroup]  (sparse)
            │               ├── DayGroup (Oct 19, 2025)
            │               │       ├── items: list[LibraryItem]
            │               │       ├── best_shots: list[LibraryItem]
            │               │       └── events: list[EventCluster]
            │               └── DayGroup (Oct 20, 2025)
            │                       └── ...
            └── MonthGroup (November 2025)
                    └── ...

LibraryItem <───────┐
    ├── exif_data   │ (referenced by all groups)
    ├── quality_score
    └── thumbnail_path

EventCluster
    └── items: list[LibraryItem]
```

---

## Index Structures (Performance)

For efficient querying, the following indices are maintained in `LibraryService`:

```python
class LibraryService:
    """Service layer for library data management."""

    # Primary data
    _items: list[LibraryItem]  # All items (chronological)

    # Indices for fast lookup
    _items_by_path: dict[Path, LibraryItem]  # O(1) lookup by path
    _items_by_date: dict[datetime.date, list[LibraryItem]]  # O(1) by date
    _items_by_month: dict[tuple[int, int], list[LibraryItem]]  # O(1) by (year, month)
    _items_by_year: dict[int, list[LibraryItem]]  # O(1) by year

    # Cached groups (computed once, invalidated on data change)
    _day_groups: dict[datetime.date, DayGroup]
    _month_groups: dict[tuple[int, int], MonthGroup]
    _year_groups: dict[int, YearGroup]
```

**Index Maintenance**:

- Indices built on initialization (O(n) scan)
- Updated incrementally on file add/remove (O(1) per operation)
- Cached groups invalidated and recomputed on demand

---

## References

- [Feature Specification](spec.md) - Requirements and user stories
- [Implementation Plan](plan.md) - Technical context
- [Research: Virtual Scrolling](research.md) - QAbstractListModel pattern
- [Research: Photo Quality](research-photo-quality-ranking.md) - Scoring algorithms
- [Research: Async Thumbnails](research-async-thumbnails.md) - Threading patterns

**Next**: [API Contracts](contracts/library_view_api.py) defining service interfaces
