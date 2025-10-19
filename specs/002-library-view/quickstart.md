# Quickstart Guide: Library View Implementation

**Feature**: Library View (002-library-view)
**Date**: 2025-10-19
**Status**: Implementation Guide

## Overview

This guide provides a step-by-step implementation path for the Library view feature, organized by priority (P1 → P2 → P3 → P4) following the progressive enhancement principle from the constitution.

**Implementation Order**:

1. **P1: All Photos View** (MVP) - Complete library grid with virtual scrolling
2. **P2: Days View** - Chronological organization with best shots
3. **P3: Months View** - Event-based clustering
4. **P4: Years View** - Highlights with temporal variety

Each phase is independently deployable and provides immediate user value.

---

## Prerequisites

Before starting implementation:

```bash
# Ensure development environment is ready
cd /home/nick/workspace/photo_organiser
uv sync --extra dev

# Verify existing services work
uv run pytest tests/test_filesystem_scanner.py -v
uv run pytest tests/test_thumbnail_cache.py -v
```

**Required Reading**:

- [Data Model](data-model.md) - Entity definitions
- [API Contracts](contracts/library_view_api.py) - Service interfaces
- [Research: Virtual Scrolling](research.md) - QListView patterns
- [Research: Async Thumbnails](research-async-thumbnails.md) - Threading
- [Research: Photo Quality](research-photo-quality-ranking.md) - Scoring

---

## Phase 1: All Photos View (P1 - MVP)

**Goal**: Scrollable grid of all photos with async thumbnail loading

**User Value**: View entire photo library in a single grid (FR-003, FR-004, FR-005)

**Time Estimate**: 2-3 days

### Step 1.1: Create Core Data Models

**Files to create**:

- `src/models/library_item.py`
- `src/models/view_groups.py` (empty for now, used in P2+)

**Implementation**:

```python
# src/models/library_item.py
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from enum import Enum

class MediaType(Enum):
    PHOTO = "photo"
    VIDEO = "video"

@dataclass
class LibraryItem:
    """See data-model.md for full definition."""
    path: Path
    media_type: MediaType
    created_date: datetime
    modified_date: datetime
    thumbnail_path: Path | None
    thumbnail_size: tuple[int, int]
    exif_data: dict
    quality_score: float | None = None  # Computed in P2
    # ... (see data-model.md for all fields)
```

**Testing**: Create `tests/test_library_item.py` with validation tests

```bash
uv run pytest tests/test_library_item.py -v
```

---

### Step 1.2: Create Library Service (Basic)

**File to create**: `src/services/library_service.py`

**Implementation**:

```python
# src/services/library_service.py
from pathlib import Path
from models.library_item import LibraryItem, MediaType
from services.filesystem_scanner import FilesystemScanner
from utils.exif_parser import ExifParser

class LibraryService:
    """
    Core service for library data management.
    Phase 1: Load all photos, no grouping/scoring yet.
    """

    def __init__(self, photo_root: Path):
        self._photo_root = photo_root
        self._scanner = FilesystemScanner(photo_root)
        self._exif_parser = ExifParser()
        self._items: list[LibraryItem] = []
        self._items_by_path: dict[Path, LibraryItem] = {}

    def load_library(self) -> None:
        """Load all photos from filesystem."""
        photo_paths = self._scanner.scan()  # Existing service

        for path in photo_paths:
            exif_data = self._exif_parser.extract(path)
            created_date = self._extract_date(exif_data, path)

            item = LibraryItem(
                path=path,
                media_type=self._detect_media_type(path),
                created_date=created_date,
                modified_date=datetime.fromtimestamp(path.stat().st_mtime),
                thumbnail_path=None,  # Generated on demand
                thumbnail_size=(200, 200),
                exif_data=exif_data,
            )
            self._items.append(item)
            self._items_by_path[path] = item

        # Sort chronologically (newest first)
        self._items.sort(key=lambda x: x.created_date, reverse=True)

    def get_all_items(self, offset: int = 0, limit: int = 200) -> list[LibraryItem]:
        """Get paginated items."""
        return self._items[offset:offset + limit]

    def get_total_count(self) -> int:
        """Total item count."""
        return len(self._items)

    # ... helper methods
```

**Testing**:

```bash
uv run pytest tests/test_library_service.py -v
```

---

### Step 1.3: Create Async Thumbnail Loader

**File to create**: `src/utils/async_loader.py`

**Implementation** (see [research-async-thumbnails.md](research-async-thumbnails.md) for full pattern):

```python
# src/utils/async_loader.py
from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal
from pathlib import Path

class WorkerSignals(QObject):
    thumbnail_ready = pyqtSignal(int, Path)  # index, thumbnail_path
    thumbnail_failed = pyqtSignal(int, str)  # index, error_message

class ThumbnailWorker(QRunnable):
    """Background worker for thumbnail generation."""

    def __init__(self, index: int, source_path: Path, size: tuple[int, int],
                 photo_processor, thumbnail_cache):
        super().__init__()
        self.signals = WorkerSignals()
        self.index = index
        self.source_path = source_path
        self.size = size
        self.photo_processor = photo_processor
        self.thumbnail_cache = thumbnail_cache

    def run(self):
        """Execute in background thread."""
        try:
            # Check cache first (mtime validation)
            cached = self.thumbnail_cache.get(self.source_path, self.size)
            if cached:
                self.signals.thumbnail_ready.emit(self.index, cached)
                return

            # Generate new thumbnail
            thumbnail_path = self.photo_processor.generate_thumbnail(
                self.source_path, self.size
            )
            if thumbnail_path:
                self.signals.thumbnail_ready.emit(self.index, thumbnail_path)
            else:
                self.signals.thumbnail_failed.emit(self.index, "Generation failed")

        except Exception as e:
            self.signals.thumbnail_failed.emit(self.index, str(e))

class ThumbnailLoader:
    """Manages async thumbnail loading with QThreadPool."""

    def __init__(self, photo_processor, thumbnail_cache):
        self.thread_pool = QThreadPool.globalInstance()
        self.photo_processor = photo_processor
        self.thumbnail_cache = thumbnail_cache

    def queue_thumbnail(self, index: int, source_path: Path,
                       size: tuple[int, int], priority: int = 0):
        """Queue thumbnail for async loading."""
        worker = ThumbnailWorker(index, source_path, size,
                                self.photo_processor, self.thumbnail_cache)
        # Connect signals in calling code
        self.thread_pool.start(worker)  # priority parameter available if needed
```

---

### Step 1.4: Create Virtual Grid Widget

**File to create**: `src/ui/widgets/virtual_grid.py`

**Implementation** (see [research.md](research.md) for full QListView pattern):

```python
# src/ui/widgets/virtual_grid.py
from PyQt6.QtWidgets import QListView, QStyledItemDelegate
from PyQt6.QtCore import QAbstractListModel, QModelIndex, Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QIcon

class PhotoLibraryModel(QAbstractListModel):
    """Virtual model for library items."""

    def __init__(self, items: list, batch_size: int = 200):
        super().__init__()
        self._items = items
        self._batch_size = batch_size
        self._loaded_count = min(batch_size, len(items))

    def rowCount(self, parent=QModelIndex()) -> int:
        return self._loaded_count

    def data(self, index: QModelIndex, role: int):
        if not index.isValid() or index.row() >= self._loaded_count:
            return None

        item = self._items[index.row()]

        if role == Qt.ItemDataRole.UserRole:
            return item  # Full item for delegate
        elif role == Qt.ItemDataRole.DisplayRole:
            return item.display_date

        return None

    def canFetchMore(self, parent=QModelIndex()) -> bool:
        return self._loaded_count < len(self._items)

    def fetchMore(self, parent=QModelIndex()):
        remaining = len(self._items) - self._loaded_count
        items_to_fetch = min(remaining, self._batch_size)

        self.beginInsertRows(QModelIndex(), self._loaded_count,
                            self._loaded_count + items_to_fetch - 1)
        self._loaded_count += items_to_fetch
        self.endInsertRows()

class ThumbnailDelegate(QStyledItemDelegate):
    """Delegate for thumbnail display with async loading."""

    thumbnail_requested = pyqtSignal(int, Path)  # index, source_path

    def __init__(self, placeholder_pixmap: QPixmap):
        super().__init__()
        self.placeholder = placeholder_pixmap
        self.thumbnail_cache = {}  # QPixmap cache (bounded externally)

    def paint(self, painter, option, index):
        item = index.data(Qt.ItemDataRole.UserRole)
        if not item:
            return

        # Check if thumbnail loaded
        pixmap = self.thumbnail_cache.get(index.row())
        if not pixmap:
            pixmap = self.placeholder
            # Emit load request (handled by view)
            self.thumbnail_requested.emit(index.row(), item.path)

        # Draw pixmap (simplified - see research.md for full implementation)
        painter.drawPixmap(option.rect, pixmap)

    def sizeHint(self, option, index):
        return QSize(200, 200)  # Uniform size (CRITICAL for performance)

class VirtualGridWidget(QListView):
    """High-performance virtual scrolling grid."""

    def __init__(self):
        super().__init__()
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setUniformItemSizes(True)  # ✅ CRITICAL for performance
        self.setIconSize(QSize(200, 200))
        # ... more configuration (see research.md)
```

---

### Step 1.5: Create All Photos Grid View

**File to create**: `src/ui/all_photos_grid.py`

**Implementation**:

```python
# src/ui/all_photos_grid.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from ui.widgets.virtual_grid import VirtualGridWidget, PhotoLibraryModel, ThumbnailDelegate
from utils.async_loader import ThumbnailLoader
from services.library_service import LibraryService

class AllPhotosGrid(QWidget):
    """All Photos view with virtual scrolling."""

    def __init__(self, library_service: LibraryService, thumbnail_loader: ThumbnailLoader):
        super().__init__()
        self.library = library_service
        self.thumbnail_loader = thumbnail_loader

        # Create grid
        self.grid = VirtualGridWidget()
        self.model = PhotoLibraryModel(self.library.get_all_items())
        self.delegate = ThumbnailDelegate(self._create_placeholder())

        self.grid.setModel(self.model)
        self.grid.setItemDelegate(self.delegate)

        # Connect signals
        self.delegate.thumbnail_requested.connect(self._on_thumbnail_requested)
        # Connect thumbnail_loader signals to update view

        layout = QVBoxLayout()
        layout.addWidget(self.grid)
        self.setLayout(layout)

    def _on_thumbnail_requested(self, index: int, source_path: Path):
        """Queue thumbnail for async loading."""
        self.thumbnail_loader.queue_thumbnail(index, source_path, (200, 200), priority=0)
```

---

### Step 1.6: Integrate into Main Window

**File to modify**: `src/ui/main_window.py`

**Changes**:

```python
# Add Library tab to main window
from ui.all_photos_grid import AllPhotosGrid

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # ... existing code

        # Create Library tab
        self.library_service = LibraryService(Path(config.photo_root))
        self.library_service.load_library()

        self.thumbnail_loader = ThumbnailLoader(photo_processor, thumbnail_cache)
        self.all_photos_view = AllPhotosGrid(self.library_service, self.thumbnail_loader)

        # Add to tab widget
        self.tabs.addTab(self.all_photos_view, "Library")
```

---

### Step 1.7: Test & Validate P1

**Manual Testing**:

1. Launch application: `uv run python src/main.py`
2. Click "Library" tab
3. Verify:
   - ✅ Grid displays all photos
   - ✅ Smooth scrolling (60fps)
   - ✅ Thumbnails load progressively
   - ✅ Can scroll through 1,000+ photos without lag
   - ✅ Memory stays <500MB

**Performance Benchmarks**:

```bash
# Use existing profile_performance.py to measure
uv run python profile_performance.py --test library_scroll --photo-count 10000
```

**Success Criteria** (from spec.md):

- ✅ SC-004: All Photos grid displays within 1 second
- ✅ SC-001: 60 fps scrolling with 10,000 photos
- ✅ SC-002: Thumbnails load within 2 seconds per viewport

---

## Phase 2: Days View (P2)

**Goal**: Organize photos by day with best shots highlighted

**User Value**: Browse photos chronologically by day (FR-007, FR-008)

**Time Estimate**: 1-2 days

### Step 2.1: Implement Photo Quality Scoring

**File to create**: `src/services/photo_quality.py`

**Implementation** (see [research-photo-quality-ranking.md](research-photo-quality-ranking.md)):

```python
# src/services/photo_quality.py
class PhotoQualityRanker:
    """EXIF-based photo quality assessment."""

    def calculate_score(self, exif_data: dict) -> float:
        """
        Return 0-100 quality score.
        Components: ISO (40%), shake (30%), aperture (15%), exposure (10%), flash (5%)
        """
        # See research-photo-quality-ranking.md for full algorithm
        pass

    def select_best_shots(self, items: list, max_count: int = 5) -> list:
        """Select top N photos by quality score."""
        scored = [item for item in items if item.quality_score is not None]
        scored.sort(key=lambda x: x.quality_score, reverse=True)
        return scored[:max_count]
```

**Modify LibraryService**:

```python
# src/services/library_service.py
def load_library(self):
    # ... existing code
    # Add quality scoring
    ranker = PhotoQualityRanker()
    for item in self._items:
        item.quality_score = ranker.calculate_score(item.exif_data)
```

---

### Step 2.2: Implement Day Grouping

**Modify**: `src/services/library_service.py`

```python
def get_days(self, year: int | None = None, month: int | None = None) -> list[DayGroup]:
    """Group items by day with best shots."""
    filtered = self._filter_by_date(self._items, year, month)

    days_dict = {}
    for item in filtered:
        day = item.created_date.date()
        if day not in days_dict:
            days_dict[day] = []
        days_dict[day].append(item)

    day_groups = []
    ranker = PhotoQualityRanker()
    for day, items in days_dict.items():
        best_shots = ranker.select_best_shots(items, max_count=5)
        day_groups.append(DayGroup(
            date=day,
            items=items,
            best_shots=best_shots,
            photo_count=sum(1 for i in items if i.media_type == MediaType.PHOTO),
            video_count=sum(1 for i in items if i.media_type == MediaType.VIDEO),
            events=[]  # Computed in P3 if needed
        ))

    return sorted(day_groups, key=lambda x: x.date, reverse=True)
```

---

### Step 2.3: Create Days View UI

**File to create**: `src/ui/days_view.py`

```python
# src/ui/days_view.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea

class DaysView(QWidget):
    """Days view with chronological organization and best shots."""

    def __init__(self, library_service: LibraryService):
        super().__init__()
        self.library = library_service

        layout = QVBoxLayout()
        scroll = QScrollArea()

        # Get day groups
        days = self.library.get_days()

        for day in days:
            # Day header
            header = QLabel(day.display_title)
            layout.addWidget(header)

            # Best shots grid (highlighted)
            best_shots_grid = self._create_best_shots_grid(day.best_shots)
            layout.addWidget(best_shots_grid)

            # All photos grid
            all_photos_grid = self._create_photos_grid(day.items)
            layout.addWidget(all_photos_grid)

        scroll.setWidget(QWidget())
        scroll.widget().setLayout(layout)
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(scroll)
```

**Add to Main Window**:

```python
self.days_view = DaysView(self.library_service)
self.tabs.addTab(self.days_view, "Days")
```

---

### Step 2.4: Test & Validate P2

**Success Criteria**:

- ✅ Days organized chronologically
- ✅ Best shots highlighted (top 5 per day)
- ✅ Performance remains smooth

---

## Phase 3: Months View (P3)

**Goal**: Organize photos by month with event clustering

**Time Estimate**: 1-2 days

### Step 3.1: Implement Event Clustering

**File to create**: `src/services/event_clustering.py`

**Implementation** (see [research-photo-quality-ranking.md](research-photo-quality-ranking.md)):

```python
# src/services/event_clustering.py
from datetime import timedelta

class EventClusterer:
    """Time-based event detection."""

    def cluster_by_time_gaps(self, items: list, gap_threshold: timedelta) -> list[EventCluster]:
        """
        O(n) gap-based clustering.
        See research-photo-quality-ranking.md for algorithm.
        """
        pass
```

---

### Step 3.2: Implement Month Grouping

**Modify**: `src/services/library_service.py`

```python
def get_months(self, year: int | None = None) -> list[MonthGroup]:
    """Group items by month with events."""
    # Similar to get_days(), but with event clustering
    clusterer = EventClusterer()
    # ...
```

---

### Step 3.3: Create Months View UI

**File to create**: `src/ui/months_view.py`

Similar pattern to Days view, but displaying events within months.

---

## Phase 4: Years View (P4)

**Goal**: Highlights from each year with temporal variety

**Time Estimate**: 1-2 days

**Implementation**: Similar pattern to P2/P3, using `select_highlights_with_variety()` from quality ranker.

---

## Integration Checklist

After all phases complete:

- [ ] All four view modes functional (All Photos, Days, Months, Years)
- [ ] View switching <500ms (SC-005)
- [ ] Filesystem watcher integration (auto-refresh, FR-023)
- [ ] Error handling (corrupted files, missing EXIF, FR-015, FR-021)
- [ ] Performance validated with 50,000 photos (SC-007)
- [ ] Memory usage <500MB (Constitution: Performance Standards)

---

## Deployment & Testing

```bash
# Run full test suite
uv run pytest tests/ -v

# Performance profiling
uv run python profile_performance.py --test library_full --photo-count 50000

# Manual testing checklist (see spec.md for acceptance scenarios)
```

---

## Troubleshooting

**Problem**: Slow scrolling

- ✅ Check `setUniformItemSizes(True)` is set
- ✅ Verify delegate doesn't do heavy computation in `paint()`
- ✅ Profile with `python -m cProfile`

**Problem**: High memory usage

- ✅ Check LRU cache is evicting old thumbnails
- ✅ Verify QPixmap not created in background threads
- ✅ Use `tracemalloc` to find leaks

**Problem**: Thumbnails not loading

- ✅ Verify signals connected properly
- ✅ Check worker thread errors (enable logging)
- ✅ Validate ThumbnailCache paths

---

## References

- [Feature Spec](spec.md)
- [Data Model](data-model.md)
- [API Contracts](contracts/library_view_api.py)
- [Research: Virtual Scrolling](research.md)
- [Research: Async Thumbnails](research-async-thumbnails.md)
- [Research: Photo Quality](research-photo-quality-ranking.md)
- [Constitution](.specify/memory/constitution.md)

**Ready for Implementation**: Use `/speckit.tasks` to generate detailed task breakdown.
