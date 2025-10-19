# Technical Research: Photo Album Organization Application

**Date**: 2025-10-15
**Updated**: 2025-10-16 (Changed UI framework from tkinter/CustomTkinter to PyQt6)
**Status**: Complete

This document captures technical research findings and decisions for implementing the photo album organization application.

## 1. Thumbnail Generation Strategy

### Decision

Use Pillow's `Image.thumbnail()` method with disk-based caching in a dedicated thumbnails directory. Generate thumbnails lazily (on-demand) and cache with SHA-256 hash of source file path as filename.

### Rationale

- **Performance**: PIL's `thumbnail()` maintains aspect ratio and is optimized for speed
- **Memory**: Disk caching prevents re-generation and bounds memory usage
- **Quality**: LANCZOS resampling provides good quality at reasonable speed
- **Standard sizes**: 200x200px for album preview, 150x150px for photo grid tiles

### Implementation Pattern

```python
from PIL import Image
import hashlib
from pathlib import Path

def generate_thumbnail(source_path: Path, size: tuple[int, int], cache_dir: Path) -> Path:
    """Generate and cache a thumbnail."""
    # Create cache key from source path
    cache_key = hashlib.sha256(str(source_path).encode()).hexdigest()
    cache_file = cache_dir / f"{cache_key}_{size[0]}x{size[1]}.jpg"

    # Return cached if exists and source hasn't changed
    if cache_file.exists():
        if cache_file.stat().st_mtime >= source_path.stat().st_mtime:
            return cache_file

    # Generate new thumbnail
    with Image.open(source_path) as img:
        img.thumbnail(size, Image.Resampling.LANCZOS)
        img.save(cache_file, "JPEG", quality=85, optimize=True)

    return cache_file
```

### Alternatives Considered

- **In-memory cache**: Rejected due to memory constraints (50k+ photos)
- **Database BLOB storage**: Rejected for complexity; filesystem is simpler
- **Pre-generation on startup**: Rejected; would violate 3s startup requirement

---

## 2. Filesystem Watching

### Decision

Use `watchdog` library with `Observer` pattern watching the root photo directory. Use event batching (500ms debounce) to avoid excessive UI updates during bulk operations.

### Rationale

- **Cross-platform**: watchdog abstracts platform differences (inotify on Linux)
- **Efficient**: Uses OS-level APIs for real-time notifications
- **Event filtering**: Can filter for directory creation/deletion and file modifications
- **Meets SC-011**: 2-second detection requirement (500ms debounce + processing)

### Implementation Pattern

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
import time

class PhotoDirectoryHandler(FileSystemEventHandler):
    def __init__(self, callback, debounce_ms=500):
        self.callback = callback
        self.debounce_ms = debounce_ms
        self.pending_events = []
        self.timer = None

    def on_any_event(self, event):
        """Queue events and debounce."""
        self.pending_events.append(event)

        # Reset debounce timer
        if self.timer:
            self.timer.cancel()
        self.timer = threading.Timer(
            self.debounce_ms / 1000,
            self._process_events
        )
        self.timer.start()

    def _process_events(self):
        """Process batched events."""
        events = self.pending_events.copy()
        self.pending_events.clear()
        self.callback(events)

# Usage
observer = Observer()
handler = PhotoDirectoryHandler(callback=ui_refresh_callback)
observer.schedule(handler, path="/photos", recursive=True)
observer.start()
```

### Alternatives Considered

- **Polling**: Rejected; inefficient for large directories, wouldn't meet 2s requirement
- **Manual refresh button only**: Rejected; spec requires auto-detection (FR-001a)

---

## 3. RAW Image Support

### Decision

**Hybrid approach**: Use Pillow for JPEG/PNG/HEIC, add `rawpy` for CR3/RAW formats. Extract embedded JPEG preview from RAW files for thumbnails (faster than full RAW decode).

### Rationale

- **Format coverage**: Pillow handles JPEG, PNG; rawpy handles CR3, NEF, ARW, etc.
- **Performance**: Extracting embedded preview is 10-100x faster than decoding RAW
- **Quality**: Embedded previews are typically 1920x1080, sufficient for thumbnails
- **Fallback**: If no preview, fall back to full decode (slower but correct)

### Implementation Pattern

```python
from PIL import Image
import rawpy

def load_image_for_thumbnail(path: Path) -> Image:
    """Load image, handling RAW formats."""
    suffix = path.suffix.lower()

    if suffix in ['.cr3', '.nef', '.arw', '.dng']:
        # RAW format - extract embedded preview
        with rawpy.imread(str(path)) as raw:
            try:
                # Try to get embedded JPEG preview (fast)
                thumb = raw.extract_thumb()
                if thumb.format == rawpy.ThumbFormat.JPEG:
                    return Image.open(io.BytesIO(thumb.data))
            except:
                pass
            # Fallback: decode full RAW (slow)
            rgb = raw.postprocess()
            return Image.fromarray(rgb)
    else:
        # Standard format
        return Image.open(path)
```

### Dependencies Added

- `rawpy` (wraps libraw for RAW decoding)
- `imagecodecs` (for HEIC support in Pillow)

### Alternatives Considered

- **External converter (dcraw)**: Rejected; adds subprocess overhead and complexity
- **Skip RAW, show placeholder**: Rejected; user has CR3 files in example directory

---

## 4. Drag-Drop in PyQt6

### Decision

Use PyQt6's native drag-and-drop system with QDrag for album reordering. For photo selection (drag-to-select), use QRubberBand for visual selection rectangle.

### Rationale

- **Native Support**: PyQt6 has built-in, robust drag-drop via QDrag and QDropEvent
- **Album DnD**: QDrag with custom mime data for reordering tiles
- **Photo Selection**: QRubberBand provides native selection rectangle
- **Cross-platform**: Works consistently across Linux, Windows, macOS

### Implementation Pattern

```python
# Album drag-drop (using PyQt6 native)
from PyQt6.QtWidgets import QWidget, QLabel
from PyQt6.QtCore import Qt, QMimeData
from PyQt6.QtGui import QDrag, QPixmap

class AlbumTile(QWidget):
    def __init__(self, parent, album):
        super().__init__(parent)
        self.album = album
        self.setAcceptDrops(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.pos()

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return

        # Start drag operation
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.album.path)
        drag.setMimeData(mime_data)
        drag.setPixmap(self.grab().scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio))
        drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        # Handle reordering
        event.acceptProposedAction()

# Photo selection (using QRubberBand)
from PyQt6.QtWidgets import QWidget, QRubberBand
from PyQt6.QtCore import QRect, QPoint

class PhotoGrid(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self.origin = QPoint()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.pos()
            self.rubber_band.setGeometry(QRect(self.origin, QSize()))
            self.rubber_band.show()

    def mouseMoveEvent(self, event):
        if self.rubber_band.isVisible():
            self.rubber_band.setGeometry(QRect(self.origin, event.pos()).normalized())
            # Highlight tiles within rectangle

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.rubber_band.hide()
            # Finalize selection
```

### Dependencies Added

- None (PyQt6 includes all drag-drop functionality)

### Alternatives Considered

- **Third-party drag-drop library**: Rejected; PyQt6 native support is comprehensive
- **Custom drag-drop implementation**: Rejected; would reinvent the wheel

---

## 5. Large Grid Performance

### Decision

Use **QListWidget with custom item delegates** or **QScrollArea with flow layout** and viewport-based rendering. PyQt6's model-view architecture provides efficient rendering of large datasets with built-in viewport culling.

### Rationale

- **Native optimization**: Qt's view classes automatically handle viewport culling
- **Memory efficient**: Only visible items are rendered/painted
- **QListWidget**: Built-in grid mode with icon view, minimal code
- **QScrollArea + Flow**: More control for custom layouts if needed
- **Meets SC-006**: Handles 500+ photos with native performance
- **Hardware acceleration**: Qt uses GPU rendering when available

### Implementation Pattern

```python
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QStyledItemDelegate
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap

class PhotoGrid(QListWidget):
    """Efficient grid view for photos using QListWidget."""

    def __init__(self, parent, item_size=(150, 150)):
        super().__init__(parent)
        self.item_size = item_size

        # Configure for grid display
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setIconSize(QSize(*item_size))
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setSpacing(10)
        self.setUniformItemSizes(True)  # Performance optimization

        # Optional: Custom delegate for advanced rendering
        self.setItemDelegate(PhotoItemDelegate())

    def load_photos(self, photos):
        """Load photos into grid (only creates items, not pixmaps)."""
        self.clear()
        for photo in photos:
            item = QListWidgetItem(photo.filename)
            item.setData(Qt.ItemDataRole.UserRole, photo)
            # Icon loaded lazily by delegate
            self.addItem(item)

class PhotoItemDelegate(QStyledItemDelegate):
    """Custom delegate for lazy thumbnail loading."""

    def paint(self, painter, option, index):
        photo = index.data(Qt.ItemDataRole.UserRole)

        # Load thumbnail only if not cached
        if not hasattr(photo, '_cached_pixmap'):
            # Load from thumbnail cache
            photo._cached_pixmap = QPixmap(photo.thumbnail_path)

        # Paint thumbnail
        painter.drawPixmap(option.rect, photo._cached_pixmap)

# Alternative: Custom QScrollArea with flow layout
class CustomPhotoGrid(QScrollArea):
    """Custom grid with viewport culling for maximum control."""

    def __init__(self, parent):
        super().__init__(parent)
        self.container = QWidget()
        self.layout = FlowLayout(self.container)
        self.setWidget(self.container)
        self.setWidgetResizable(True)

    def paintEvent(self, event):
        """Only paint items in visible viewport."""
        viewport_rect = self.viewport().rect()
        # Paint only widgets intersecting viewport
        super().paintEvent(event)
```

### Key Advantages

- **Built-in viewport culling**: Qt only renders visible items
- **Efficient scrolling**: Hardware-accelerated by Qt
- **Minimal code**: QListWidget IconMode handles grid layout
- **Lazy loading**: Custom delegates load thumbnails on-demand

### Alternatives Considered

- **QTableWidget**: Rejected; less efficient for uniform grids
- **Custom widget tree**: Rejected; Qt's views already optimized
- **Full manual viewport culling**: Rejected; Qt handles this natively

---

## 6. JSON State Format

### Decision

Use JSON file for application state instead of SQLite. Store minimal state with single `album_order` array for user-defined album ordering.

### Rationale

- **Minimal state**: Only album order needs persistence (filesystem is source of truth)
- **Simplicity**: Simple JSON structure, no database setup needed
- **Human-readable**: Easy to inspect and debug
- **Flexibility**: Can extend with additional fields without schema migrations
- **Performance**: Small dataset (<10k albums), file I/O is fast enough

### JSON Structure

```json
{
  "version": "1.0",
  "album_order": [
    {
      "album_path": "/absolute/path/to/album1",
      "sort_index": 0,
      "metadata": {
        "pinned": false,
        "custom_name": null
      },
      "updated_at": "2025-10-16T14:30:00Z"
    }
  ]
}
```

### Access Pattern

```python
import json
from pathlib import Path
from datetime import datetime

class AppState:
    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.data = self.load()

    def load(self) -> dict:
        """Load state from JSON file."""
        if not self.state_file.exists():
            return {"version": "1.0", "album_order": []}

        with open(self.state_file, 'r') as f:
            return json.load(f)

    def save(self):
        """Save state to JSON file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(self.data, f, indent=2)

    def get_album_order(self) -> list[dict]:
        """Get all albums with their sort order."""
        return sorted(
            self.data.get('album_order', []),
            key=lambda x: x['sort_index']
        )

    def set_album_order(self, album_path: str, sort_index: int):
        """Set album sort order."""
        orders = self.data.get('album_order', [])

        # Update existing or add new
        for order in orders:
            if order['album_path'] == album_path:
                order['sort_index'] = sort_index
                order['updated_at'] = datetime.utcnow().isoformat() + 'Z'
                break
        else:
            orders.append({
                'album_path': album_path,
                'sort_index': sort_index,
                'metadata': {},
                'updated_at': datetime.utcnow().isoformat() + 'Z'
            })

        self.data['album_order'] = orders
        self.save()
```

### Alternatives Considered

- **SQLite database**: Rejected; overkill for simple key-value storage
- **TOML/YAML**: Rejected; JSON is simpler and stdlib-supported
- **Binary format (pickle)**: Rejected; not human-readable, security concerns

---

## Summary of Dependencies

### Required Libraries

```toml
[project]
dependencies = [
    "PyQt6>=6.5.0",             # GUI framework with native widgets
    "pillow>=10.0.0",           # Image processing, thumbnails
    "watchdog>=3.0.0",          # Filesystem monitoring
    "rawpy>=0.18.0",            # RAW image support (CR3, NEF, etc)
    "exifread>=3.0.0",          # EXIF metadata parsing
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",            # Testing framework
    "pytest-qt>=4.2.0",         # PyQt testing utilities
    "ruff>=0.1.0",              # Linting and formatting
]
```

### System Dependencies (Linux)

- Python 3.13
- PyQt6 system libraries (usually installed with pip package)
- libraw (for rawpy, install via `apt install libraw-dev`)

---

## Performance Validation

### Expected Performance Characteristics

| Metric | Target | Implementation Strategy |
|--------|--------|------------------------|
| Startup time | <2s | Lazy loading; defer thumbnail generation |
| Thumbnail generation | <500ms/image | PIL optimized; cached on disk |
| UI responsiveness | <100ms | Qt viewport culling; hardware-accelerated rendering |
| Filesystem detection | <2s | watchdog with 500ms debounce |
| Memory usage | <500MB | Qt viewport culling; disk cache |
| Large album (500 photos) | No lag | QListWidget with lazy delegates; native optimization |

### Bottleneck Mitigation

1. **Thumbnail generation**: Disk caching + lazy loading
2. **Large grids**: Qt viewport culling + item delegates (only paint visible)
3. **Filesystem watching**: Event batching (debounce)
4. **RAW decoding**: Extract embedded preview (10-100x faster)
5. **UI rendering**: Qt hardware acceleration + efficient paint events

---

## Open Questions / Future Considerations

1. **Multi-threading**: Consider thread pool for parallel thumbnail generation (future optimization)
2. **Progressive loading**: Show placeholder → thumbnail → full quality (future UX enhancement)
3. **Thumbnail cleanup**: Add periodic cache cleanup for deleted source files (low priority)
4. **Configuration file**: Add TOML config for photo directory path, thumbnail size (future)

---

**Research Status**: ✅ Complete - All technical unknowns resolved. Ready for Phase 1 (Data Model & Contracts).
