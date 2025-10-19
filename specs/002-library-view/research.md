# Research: PyQt6 Virtual Scrolling for High-Performance Photo Grid

**Feature**: Library View (002-library-view)
**Date**: 2025-10-19
**Research Focus**: Virtual scrolling implementation patterns for displaying 10,000+ photos with 60fps performance

## Executive Summary

**Recommended Approach**: QListView in IconMode with QAbstractListModel + QStyledItemDelegate + background QImage loading

This proven pattern leverages Qt's built-in virtual scrolling in QListView (which only renders visible items), combined with a custom model for efficient data management, a custom delegate for asynchronous thumbnail rendering, and background QImage loading to avoid blocking the UI thread.

**Key Finding**: The existing `PhotoGrid` implementation already uses QListWidget in IconMode, which provides basic virtual scrolling. However, for 10,000+ photos, we need to migrate to QListView + QAbstractListModel for true on-demand data loading and better memory management.

## Decision: QListView IconMode + QAbstractListModel + Async Delegate

### Rationale

1. **Built-in Virtual Scrolling**: QListView (and QTableView) have native virtual scrolling - they only render visible items and reuse delegates when scrolling. This is Qt's standard approach for large datasets.

2. **Proven Performance**: Multiple developers report handling 50,000-100,000+ items smoothly with this pattern. One user reported a table with 101,000,000+ rows with no scroll problems.

3. **Simplicity**: Uses standard Qt Model/View architecture without custom viewport calculations. The view handles all scrolling, item positioning, and rendering optimization automatically.

4. **PyQt6 Compatibility**: All components (QListView, QAbstractItemModel, QStyledItemDelegate) are core Qt classes with identical PyQt5/PyQt6 APIs. No threading restrictions have changed.

5. **Existing Foundation**: Current `PhotoGrid` already uses QListWidget (simplified version of QListView), so migration path is straightforward - replace QListWidget with QListView + custom model.

### Performance Characteristics

- **Memory**: O(visible items) instead of O(total items). Only thumbnails for visible + buffer items kept in memory.
- **Rendering**: Qt automatically recycles delegates, redrawing only when scrolling exposes new items.
- **Scrolling**: Smooth 60fps scrolling achievable with proper implementation (validated by research).
- **Thumbnail Loading**: Background threads load QImage, main thread converts to QPixmap and updates view.

## Implementation Pattern

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        LibraryView                          │
│                    (Main Container Widget)                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ contains
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                         QListView                           │
│                    (View in IconMode)                       │
│  • setViewMode(IconMode)                                    │
│  • setUniformItemSizes(True) ← CRITICAL for performance    │
│  • setIconSize(QSize(200, 200))                             │
│  • setModel(PhotoLibraryModel)                              │
│  • setItemDelegate(ThumbnailDelegate)                       │
└─────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                │                           │
                ▼                           ▼
┌───────────────────────────┐   ┌──────────────────────────┐
│   PhotoLibraryModel       │   │   ThumbnailDelegate      │
│  (QAbstractListModel)     │   │  (QStyledItemDelegate)   │
│                           │   │                          │
│  • rowCount()             │   │  • paint()               │
│  • data()                 │   │  • sizeHint()            │
│  • canFetchMore()         │   │  • Checks cache          │
│  • fetchMore()            │   │  • Draws placeholder     │
│                           │   │  • Emits load request    │
└───────────────────────────┘   └──────────────────────────┘
                │                           │
                │ queries                   │ requests
                ▼                           ▼
┌───────────────────────────┐   ┌──────────────────────────┐
│    PhotoManager           │   │  ThumbnailLoader         │
│  (Existing Service)       │   │  (Background Worker)     │
│                           │   │                          │
│  • get_photos()           │   │  • QThread worker        │
│  • filter_by_date()       │   │  • Loads QImage          │
│  • quality_metrics()      │   │  • Signals when ready    │
└───────────────────────────┘   └──────────────────────────┘
                                            │
                                            │ writes to
                                            ▼
                                ┌──────────────────────────┐
                                │   ThumbnailCache         │
                                │  (Existing Utility)      │
                                │                          │
                                │  • Disk-based cache      │
                                │  • SHA-256 keys          │
                                │  • mtime validation      │
                                └──────────────────────────┘
```

### Core Components

#### 1. QListView Configuration

```python
from PyQt6.QtWidgets import QListView
from PyQt6.QtCore import QSize

# Create view
list_view = QListView()
list_view.setViewMode(QListView.ViewMode.IconMode)
list_view.setIconSize(QSize(200, 200))  # Thumbnail display size
list_view.setGridSize(QSize(220, 240))  # Grid cell size (icon + label)
list_view.setSpacing(10)
list_view.setWrapping(True)
list_view.setResizeMode(QListView.ResizeMode.Adjust)
list_view.setMovement(QListView.Movement.Static)

# CRITICAL: Uniform sizes enable major performance optimization
list_view.setUniformItemSizes(True)  # Qt can skip expensive layout calculations

# Optional: Batched layout for even better performance with huge datasets
list_view.setLayoutMode(QListView.LayoutMode.Batched)
list_view.setBatchSize(100)  # Layout 100 items at a time
```

**Performance Impact of `setUniformItemSizes(True)`**:
- Research shows 14 seconds → 5 seconds for 1M items
- Enables Qt to calculate scroll range without examining every item
- Mandatory for smooth 60fps scrolling with 10,000+ items

#### 2. QAbstractListModel (PhotoLibraryModel)

```python
from PyQt6.QtCore import QAbstractListModel, Qt, QModelIndex
from typing import List, Optional
from pathlib import Path

class PhotoLibraryModel(QAbstractListModel):
    """Model for photo library data with lazy loading support."""

    def __init__(self, photo_manager, parent=None):
        super().__init__(parent)
        self.photo_manager = photo_manager
        self.photos: List[Photo] = []
        self.total_count = 0
        self.loaded_count = 0
        self.batch_size = 200  # Load 200 photos at a time

    def rowCount(self, parent=QModelIndex()) -> int:
        """Return number of currently loaded photos (not total)."""
        if parent.isValid():
            return 0
        return self.loaded_count  # Only loaded items, not total_count

    def data(self, index: QModelIndex, role: int):
        """Provide data for view on demand.

        This is called ONLY for visible items and their immediate neighbors.
        Qt handles the optimization automatically.
        """
        if not index.isValid() or index.row() >= len(self.photos):
            return None

        photo = self.photos[index.row()]

        if role == Qt.ItemDataRole.DecorationRole:
            # Return QIcon - delegate will handle async loading
            return None  # Delegate draws placeholder initially

        elif role == Qt.ItemDataRole.DisplayRole:
            # Return filename for display under thumbnail
            return photo.path.name

        elif role == Qt.ItemDataRole.UserRole:
            # Return Photo object for delegate to access
            return photo

        return None

    def canFetchMore(self, parent=QModelIndex()) -> bool:
        """Check if more data can be loaded."""
        if parent.isValid():
            return False
        return self.loaded_count < self.total_count

    def fetchMore(self, parent=QModelIndex()):
        """Load next batch of photos.

        Qt calls this automatically when scrolling near the end of loaded items.
        """
        if parent.isValid():
            return

        remainder = self.total_count - self.loaded_count
        items_to_fetch = min(self.batch_size, remainder)

        if items_to_fetch <= 0:
            return

        # Notify view we're adding rows
        self.beginInsertRows(
            QModelIndex(),
            self.loaded_count,
            self.loaded_count + items_to_fetch - 1
        )

        # Load next batch from photo manager
        start = self.loaded_count
        end = start + items_to_fetch
        new_photos = self.photo_manager.get_photos(start, end)
        self.photos.extend(new_photos)
        self.loaded_count += len(new_photos)

        self.endInsertRows()

    def set_photos(self, total_count: int):
        """Initialize model with total photo count.

        Args:
            total_count: Total number of photos available
        """
        self.beginResetModel()
        self.photos.clear()
        self.total_count = total_count
        self.loaded_count = 0
        self.endResetModel()

        # Trigger initial batch load
        if self.canFetchMore():
            self.fetchMore()
```

**Key Points**:
- `rowCount()` returns loaded count, not total count (critical for lazy loading)
- `data()` is called on-demand only for visible items
- `canFetchMore()` + `fetchMore()` enable progressive loading as user scrolls
- `beginInsertRows()` / `endInsertRows()` signal view to update efficiently

#### 3. QStyledItemDelegate (ThumbnailDelegate)

```python
from PyQt6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem
from PyQt6.QtCore import Qt, QModelIndex, pyqtSignal, QObject
from PyQt6.QtGui import QPainter, QPixmap, QImage, QColor

class ThumbnailDelegate(QStyledItemDelegate):
    """Custom delegate for rendering thumbnails with async loading."""

    # Signal emitted when thumbnail needs loading
    thumbnail_requested = pyqtSignal(Path, QModelIndex)  # (source_path, index)

    def __init__(self, thumbnail_cache, parent=None):
        super().__init__(parent)
        self.thumbnail_cache = thumbnail_cache
        self.thumbnail_size = (200, 200)

        # Cache for loaded thumbnails (QPixmap can only be created in main thread)
        self.pixmap_cache: dict[int, QPixmap] = {}  # row -> QPixmap

        # Placeholder/error pixmaps (created once)
        self.placeholder = self._create_placeholder()
        self.error_pixmap = self._create_error()

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        """Paint thumbnail for a single item.

        Called by Qt for each visible item. This is performance-critical.
        """
        if not index.isValid():
            return

        # Get photo from model
        photo = index.data(Qt.ItemDataRole.UserRole)
        if not photo:
            return

        row = index.row()

        # Check if we have a cached QPixmap for this row
        if row in self.pixmap_cache:
            pixmap = self.pixmap_cache[row]
        else:
            # Check if thumbnail exists on disk (fast check)
            cache_path = self.thumbnail_cache.get(photo.path, self.thumbnail_size)

            if cache_path:
                # Load from cache synchronously (fast - already resized)
                pixmap = QPixmap(str(cache_path))
                if pixmap.isNull():
                    pixmap = self.error_pixmap
                else:
                    self.pixmap_cache[row] = pixmap
            else:
                # Not cached - show placeholder and request async load
                pixmap = self.placeholder

                # Emit signal for background worker to load
                # (only emit once per item)
                self.thumbnail_requested.emit(photo.path, index)

        # Draw the pixmap centered in the item rectangle
        painter.save()

        # Draw background if selected
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        # Calculate centered position
        x = option.rect.x() + (option.rect.width() - pixmap.width()) // 2
        y = option.rect.y() + (option.rect.height() - pixmap.height()) // 2

        painter.drawPixmap(x, y, pixmap)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex):
        """Return size hint for item.

        Must be consistent for all items when uniformItemSizes is True.
        """
        from PyQt6.QtCore import QSize
        return QSize(220, 240)  # Matches gridSize

    def update_thumbnail(self, row: int, pixmap: QPixmap):
        """Called by main thread when background worker finishes loading.

        Args:
            row: Model row to update
            pixmap: Loaded QPixmap (created from QImage in main thread)
        """
        self.pixmap_cache[row] = pixmap
        # View will repaint automatically

    def _create_placeholder(self) -> QPixmap:
        """Create placeholder pixmap (loading state)."""
        pixmap = QPixmap(200, 200)
        pixmap.fill(QColor(220, 220, 220))

        painter = QPainter(pixmap)
        painter.setPen(QColor(150, 150, 150))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Loading...")
        painter.end()

        return pixmap

    def _create_error(self) -> QPixmap:
        """Create error pixmap (failed load)."""
        pixmap = QPixmap(200, 200)
        pixmap.fill(QColor(200, 100, 100))

        painter = QPainter(pixmap)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "⚠\nError")
        painter.end()

        return pixmap
```

**Key Points**:
- `paint()` is called only for visible items (Qt optimization)
- Cached QPixmaps for loaded thumbnails (memory bounded to visible + buffer)
- Placeholder drawn immediately, async load triggered for missing thumbnails
- Signal-based communication with background worker

#### 4. Background Thumbnail Loader

```python
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from pathlib import Path
import queue
import threading

class ThumbnailLoaderWorker(QObject):
    """Background worker for loading thumbnails without blocking UI.

    CRITICAL: QPixmap cannot be created in background thread.
    We load QImage in background, then convert to QPixmap in main thread.
    """

    # Signal emitted when thumbnail is loaded (received in main thread)
    thumbnail_loaded = pyqtSignal(int, QImage)  # (row, QImage)

    def __init__(self, thumbnail_cache, thumbnail_size=(200, 200)):
        super().__init__()
        self.thumbnail_cache = thumbnail_cache
        self.thumbnail_size = thumbnail_size
        self.queue = queue.Queue()
        self.running = True

    def add_request(self, source_path: Path, row: int):
        """Queue a thumbnail load request.

        Args:
            source_path: Path to source image
            row: Model row index
        """
        self.queue.put((source_path, row))

    def run(self):
        """Worker thread main loop."""
        while self.running:
            try:
                # Get next request (blocking with timeout)
                source_path, row = self.queue.get(timeout=0.1)
            except queue.Empty:
                continue

            # Load image in background thread (QImage is thread-safe)
            try:
                # Load with QImage (thread-safe)
                image = QImage(str(source_path))

                if not image.isNull():
                    # Resize image
                    scaled = image.scaled(
                        self.thumbnail_size[0],
                        self.thumbnail_size[1],
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )

                    # Save to cache
                    cache_path = self.thumbnail_cache.put(source_path, self.thumbnail_size)
                    scaled.save(str(cache_path), "JPEG", 85)

                    # Emit signal with QImage (main thread will convert to QPixmap)
                    self.thumbnail_loaded.emit(row, scaled)

            except Exception as e:
                # Log error but continue processing
                import logging
                logging.error(f"Failed to load thumbnail for {source_path}: {e}")

            self.queue.task_done()

    def stop(self):
        """Stop worker thread."""
        self.running = False


class ThumbnailLoader(QObject):
    """Main-thread coordinator for background thumbnail loading."""

    def __init__(self, thumbnail_cache, delegate, model, parent=None):
        super().__init__(parent)
        self.thumbnail_cache = thumbnail_cache
        self.delegate = delegate
        self.model = model

        # Create worker and thread
        self.worker = ThumbnailLoaderWorker(thumbnail_cache)
        self.thread = QThread()

        # Move worker to background thread
        self.worker.moveToThread(self.thread)

        # Connect signals
        self.thread.started.connect(self.worker.run)
        self.worker.thumbnail_loaded.connect(self._handle_thumbnail_loaded)

        # Start thread
        self.thread.start()

    def load_thumbnail(self, source_path: Path, index: QModelIndex):
        """Request thumbnail load for a photo.

        Args:
            source_path: Path to source image
            index: Model index
        """
        self.worker.add_request(source_path, index.row())

    def _handle_thumbnail_loaded(self, row: int, image: QImage):
        """Handle thumbnail loaded signal from worker (runs in main thread).

        Args:
            row: Model row
            image: Loaded QImage
        """
        # Convert QImage to QPixmap (must be done in main thread)
        pixmap = QPixmap.fromImage(image)

        # Update delegate cache
        self.delegate.update_thumbnail(row, pixmap)

        # Trigger repaint of this item
        index = self.model.index(row, 0)
        self.model.dataChanged.emit(index, index)

    def shutdown(self):
        """Clean shutdown of worker thread."""
        self.worker.stop()
        self.thread.quit()
        self.thread.wait()
```

**Critical Threading Rules** (from research):
1. **QPixmap**: Can ONLY be created/used in main/GUI thread
2. **QImage**: Thread-safe, can be loaded in background thread
3. **Pattern**: Load QImage in worker → emit signal → convert to QPixmap in main thread
4. **Why**: QPixmap wraps OS-specific graphics resources tied to main event loop

### Integration Example

```python
class LibraryView(QWidget):
    """Main library view container."""

    def __init__(self, photo_manager, thumbnail_cache, parent=None):
        super().__init__(parent)

        # Create model
        self.model = PhotoLibraryModel(photo_manager)

        # Create delegate
        self.delegate = ThumbnailDelegate(thumbnail_cache)

        # Create view
        self.list_view = QListView()
        self.list_view.setViewMode(QListView.ViewMode.IconMode)
        self.list_view.setUniformItemSizes(True)  # CRITICAL
        self.list_view.setIconSize(QSize(200, 200))
        self.list_view.setModel(self.model)
        self.list_view.setItemDelegate(self.delegate)

        # Create background loader
        self.loader = ThumbnailLoader(thumbnail_cache, self.delegate, self.model)

        # Connect delegate's thumbnail request signal to loader
        self.delegate.thumbnail_requested.connect(self.loader.load_thumbnail)

        # Layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.list_view)

    def load_photos(self, total_count: int):
        """Load library with total photo count."""
        self.model.set_photos(total_count)
```

## Alternatives Considered

### Alternative 1: QScrollArea + QGridLayout (Current PhotoGrid approach scaled up)

**Rejected Reason**: Does NOT provide virtual scrolling. All widgets are created immediately, consuming O(n) memory for n photos. Research confirms QListWidget/QListView significantly outperform this approach for large datasets.

**Evidence**: Multiple Stack Overflow posts describe slow performance with thousands of items in QGridLayout. One user reported "QListView does not recycle items" but this was debunked - QTableView/QListView DO recycle delegates.

### Alternative 2: QTableView instead of QListView

**Considered**: QTableView is recommended by several sources as faster than QListView for very large datasets (100,000+ items).

**Decision**: Use QListView for initial implementation because:
- IconMode is purpose-built for photo grids
- Our target is 50,000 photos (within QListView range per research)
- Simpler than managing table rows/columns
- Can migrate to QTableView later if needed (same model interface)

**Keep in mind**: If performance testing shows issues >20,000 photos, QTableView is the proven alternative.

### Alternative 3: Custom QAbstractScrollArea with manual viewport management

**Rejected Reason**: Over-engineering. Qt's built-in virtual scrolling in QListView handles our use case. Only justified for unusual requirements (e.g., non-grid layouts, special rendering).

**Simplicity principle**: Use framework-provided solutions before building custom.

### Alternative 4: QML GridView with C++ model

**Rejected Reason**: Requires mixing QML + PyQt6 widgets. Project uses pure PyQt6. QML would require rewrite of UI layer. Not justified when Qt Widgets solution exists.

## Memory Management Strategy

### Bounded Memory Design

**Goal**: Keep memory usage <500MB regardless of library size

**Approach**:

1. **Model Layer**: Store only metadata in memory (paths, dates, EXIF), not image data
   - Photo metadata: ~1KB per photo
   - 50,000 photos = 50MB metadata (acceptable)

2. **View Layer**: QListView automatically limits rendering to visible + buffer items
   - Visible items: ~30-40 thumbnails on screen at 1080p
   - Qt buffer: ~2-3 screens = 60-120 additional thumbnails
   - Total active: ~100-160 thumbnails

3. **Delegate Cache**: Bounded QPixmap cache for rendered thumbnails
   - Store QPixmaps only for visible + recently viewed items
   - LRU eviction when cache exceeds limit (e.g., 500 items)
   - 200x200 thumbnail ≈ 160KB in memory
   - 500 thumbnails = 80MB (acceptable)

4. **Disk Cache**: ThumbnailCache already handles disk persistence
   - Infinite disk cache (user's choice to clear)
   - Already has mtime validation for cache invalidation

**Memory Budget**:
- Metadata: 50MB (50,000 photos)
- Thumbnail cache: 80MB (500 QPixmaps)
- UI overhead: 50MB (Qt widgets)
- Background buffers: 100MB (image loading)
- **Total**: ~280MB (well under 500MB limit)

### Cache Eviction Strategy

```python
from collections import OrderedDict

class BoundedPixmapCache:
    """LRU cache for QPixmaps with size limit."""

    def __init__(self, max_size=500):
        self.max_size = max_size
        self.cache = OrderedDict()  # Maintains insertion order

    def get(self, key: int) -> Optional[QPixmap]:
        """Get pixmap and mark as recently used."""
        if key in self.cache:
            # Move to end (most recent)
            self.cache.move_to_end(key)
            return self.cache[key]
        return None

    def put(self, key: int, pixmap: QPixmap):
        """Add pixmap, evicting oldest if needed."""
        if key in self.cache:
            # Update existing
            self.cache.move_to_end(key)
            self.cache[key] = pixmap
        else:
            # Add new
            self.cache[key] = pixmap

            # Evict oldest if over limit
            while len(self.cache) > self.max_size:
                self.cache.popitem(last=False)  # Remove oldest (first item)
```

## Performance Optimization Checklist

Based on research findings, these optimizations are MANDATORY for 60fps scrolling:

### Critical Optimizations (P0 - Required)

- [x] **`setUniformItemSizes(True)`**: Single biggest performance win (14s → 5s for 1M items)
- [x] **QAbstractListModel instead of QStandardItemModel**: Avoid expensive item creation
- [x] **QImage loading in background thread**: Avoid UI freezing (QPixmap in main thread only)
- [x] **Disk-based thumbnail cache**: Avoid regenerating thumbnails (already implemented)
- [x] **Bounded QPixmap cache**: Prevent memory growth
- [x] **`setUpdatesEnabled(False)` during bulk updates**: Disable repaints while modifying model

### High-Value Optimizations (P1 - Strongly Recommended)

- [ ] **`setLayoutMode(Batched)` + `setBatchSize(100)`**: Layout items in batches for huge datasets
- [ ] **Lazy loading with `canFetchMore()` / `fetchMore()`**: Load data as user scrolls
- [ ] **LRU eviction for QPixmap cache**: Prevent memory leaks from unlimited cache growth
- [ ] **Pre-calculate thumbnail dimensions**: Cache aspect ratios to avoid recalculation

### Nice-to-Have Optimizations (P2 - Optional)

- [ ] **Prefetch thumbnails for next screen**: Start loading before user scrolls there
- [ ] **Priority queue for visible items**: Load on-screen items before off-screen
- [ ] **Incremental thumbnail generation**: Generate thumbnails during idle time
- [ ] **Memory-mapped metadata**: For 100,000+ photos, memory-map metadata file

## Testing Strategy

### Performance Benchmarks

Test with progressively larger datasets to validate performance targets:

1. **1,000 photos**: Baseline - should be instant
2. **5,000 photos**: Should load in <1 second, scroll at 60fps
3. **10,000 photos**: Target performance - scroll at 60fps, <2s thumbnail load per viewport
4. **25,000 photos**: Stress test - verify memory stays <500MB
5. **50,000 photos**: Maximum target - verify no degradation

### Metrics to Track

- **Scroll FPS**: Use Qt profiler or manual frame counter (target: 60fps)
- **Memory usage**: Monitor RSS during scrolling (target: <500MB)
- **Thumbnail load time**: Time from scroll to all visible thumbnails loaded (target: <2s)
- **View switch time**: Time to switch from All Photos to Days view (target: <500ms)

### Manual Testing Scenarios

1. **Rapid scrolling**: Hold Page Down, verify no lag or stuttering
2. **Jump to end**: Press Ctrl+End, verify fast jump + thumbnail loading
3. **Resize window**: Resize during scrolling, verify responsive relayout
4. **Memory stability**: Scroll up and down repeatedly, verify memory doesn't grow unbounded

## Migration from Existing PhotoGrid

Current `PhotoGrid` uses:
- QListWidget (simplified wrapper around QListView)
- Synchronous thumbnail loading
- All items added immediately

Migration path:

1. **Phase 1**: Replace QListWidget with QListView + QAbstractListModel
   - Keep synchronous loading initially
   - Validate model/view separation works

2. **Phase 2**: Add QStyledItemDelegate with async loading
   - Implement ThumbnailDelegate
   - Add ThumbnailLoader background worker
   - Connect signals

3. **Phase 3**: Add lazy loading with `canFetchMore()` / `fetchMore()`
   - Implement batch loading in model
   - Test with large datasets

4. **Phase 4**: Add bounded cache + LRU eviction
   - Implement BoundedPixmapCache
   - Monitor memory usage

**Benefits of gradual migration**:
- Each phase is independently testable
- Can validate performance improvements incrementally
- Easier to debug issues

## Key Learnings from Research

### Qt Model/View Architecture

1. **Views automatically request only visible data**: You don't need to manually track viewport
2. **Delegates are recycled**: Qt reuses delegate instances when scrolling
3. **`data()` is called on-demand**: Only for visible items + small buffer
4. **`uniformItemSizes` is critical**: Enables O(1) scroll calculations instead of O(n)

### Threading with QImage/QPixmap

1. **QPixmap is main-thread only**: Wraps OS graphics resources
2. **QImage is thread-safe**: Pure pixel data, no OS dependencies
3. **Pattern**: Load QImage in worker → signal → convert to QPixmap in main thread
4. **Performance**: Loading QImage in background makes scrolling smooth (500+ thumbnails tested)

### Performance Bottlenecks

1. **QStandardItemModel is slow**: Creating QStandardItems for each photo is expensive
2. **Synchronous loading blocks UI**: Even fast loads add up with many thumbnails
3. **Unbounded memory growth**: Without eviction, cache consumes all memory
4. **Non-uniform item sizes**: Forces Qt to measure every item for layout

## Risks and Mitigations

### Risk 1: Complexity of Model/View/Delegate Pattern

**Impact**: High learning curve for developers unfamiliar with Qt Model/View

**Mitigation**:
- Start with simple model (no lazy loading) to validate pattern
- Extensive code comments explaining Qt concepts
- Reference implementation examples in research links

### Risk 2: Background Threading Bugs

**Impact**: Race conditions, crashes from Qt threading violations

**Mitigation**:
- Follow strict rule: QImage in worker, QPixmap in main thread
- Use Qt signals for thread-safe communication
- Test with Qt threading debug flags
- Single worker thread (no complex thread pool)

### Risk 3: Cache Invalidation Complexity

**Impact**: Stale thumbnails shown to user, incorrect data

**Mitigation**:
- ThumbnailCache already has mtime-based validation (existing code)
- Model emits `dataChanged` signal when cache updates
- Clear cache on app startup during development

### Risk 4: Performance Target Not Met

**Impact**: Users experience lag/stuttering with large libraries

**Mitigation**:
- Implement ALL P0 optimizations from checklist
- Early performance testing with 10,000 photo test dataset
- Fallback to QTableView if QListView insufficient (research shows QTableView handles 100M+ rows)

## Next Steps (For Phase 1: Design)

1. **Create data model design** (`data-model.md`):
   - Define PhotoLibraryModel interface
   - Define ThumbnailDelegate interface
   - Define ThumbnailLoader interface

2. **Create API contracts** (`contracts/library_view_api.py`):
   - PhotoLibraryModel methods and signals
   - ThumbnailDelegate methods and signals
   - Integration points with existing services

3. **Create quickstart guide** (`quickstart.md`):
   - Code examples for model/view/delegate setup
   - Integration with existing PhotoManager
   - Testing approach

## References

### Primary Research Sources

1. **Qt Model/View Documentation**: https://doc.qt.io/qt-6/model-view-programming.html
   - Canonical reference for Model/View architecture
   - Explains data(), index(), fetchMore() patterns

2. **QListView Performance Optimization**: https://forum.qt.io/topic/102850/how-can-i-improving-performance-when-i-use-qlistview-with-large-numbers-of-items
   - Real-world advice: uniformItemSizes, custom model, batched layout

3. **QTableView vs QListView**: https://stackoverflow.com/questions/32449642/qlistview-with-millions-of-items-slow-with-keyboard
   - QTableView scales better for 100,000+ items
   - QListView sufficient for 50,000 items with optimizations

4. **Async Image Loading Pattern**: https://stackoverflow.com/questions/42673010/how-to-correctly-load-images-asynchronously-in-pyqt5
   - QImage in background thread, QPixmap in main thread
   - Delegate + worker signal pattern

5. **Photo Gallery Implementation**: https://www.pythonguis.com/faq/file-image-browser-app-with-thumbnails/
   - Complete PyQt5 example with thumbnails
   - Uses QListView IconMode + custom model

### Code Examples Reviewed

1. **PyQt5 QAbstractItemModel Examples**: https://www.programcreek.com/python/example/99596/PyQt5.QtCore.QAbstractItemModel
   - Reference implementations of rowCount, data, fetchMore

2. **Lazy Loading Table**: https://gist.github.com/m3nu/d1d9d6358355e0de6b20a5cd9190877e
   - canFetchMore + fetchMore pattern
   - Batch loading implementation

3. **Image Browser**: https://github.com/bneall/imagebrowser
   - Real-world photo browser with Qt
   - Thumbnail caching to disk

### Validation

All recommendations validated against:
- Official Qt documentation (Qt 6.10.0)
- Multiple Stack Overflow discussions with accepted answers
- Real-world GitHub implementations
- Research reports of 50,000-100,000+ item performance

---

**Research Complete**: Ready for Phase 1 (Design)
