# Technical Research: Photo Album Organization Application

**Date**: 2025-10-15
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

## 4. Drag-Drop in tkinter

### Decision

Use native tkinter drag-drop with TkinterDnD2 library for album reordering. For photo selection (drag-to-select), implement custom mouse event handling without DnD library.

### Rationale

- **Album DnD**: TkinterDnD2 provides robust drag-drop for reordering tiles
- **Photo selection**: Custom implementation simpler for selection rectangle
- **No CustomTkinter DnD**: CustomTkinter doesn't have built-in DnD; TkinterDnD2 compatible

### Implementation Pattern

```python
# Album drag-drop (using TkinterDnD2)
from tkinterdnd2 import DND_FILES, TkinterDnD

class AlbumTile(tk.Frame):
    def __init__(self, parent, album):
        super().__init__(parent)
        self.album = album

        # Make draggable
        self.bind("<Button-1>", self.on_drag_start)
        self.bind("<B1-Motion>", self.on_drag_motion)
        self.bind("<ButtonRelease-1>", self.on_drag_end)

# Photo selection (custom)
class PhotoGrid(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.selection_rect = None
        self.selection_start = None

        self.bind("<Button-1>", self.on_selection_start)
        self.bind("<B1-Motion>", self.on_selection_drag)
        self.bind("<ButtonRelease-1>", self.on_selection_end)

    def on_selection_drag(self, event):
        """Draw selection rectangle."""
        if self.selection_start:
            # Calculate and draw rectangle
            x0, y0 = self.selection_start
            x1, y1 = event.x, event.y
            # Highlight tiles within rectangle
```

### Dependencies Added

- `tkinterdnd2` (for album drag-drop)

### Alternatives Considered

- **Pure tkinter DnD**: Rejected; low-level and error-prone
- **CustomTkinter DnD**: Not available; would need custom implementation

---

## 5. Large Grid Performance

### Decision

Implement **virtual scrolling** using tkinter Canvas with only visible tiles rendered. Render tiles in viewport ±1 screen buffer, destroy off-screen tiles to bound memory.

### Rationale

- **Memory bound**: Only ~50-100 tiles in memory vs. thousands
- **Smooth scrolling**: Canvas provides hardware-accelerated scrolling
- **Meets SC-006**: Handles 500 photos without degradation
- **Implementation complexity**: Moderate but necessary for performance

### Implementation Pattern

```python
class VirtualGrid(tk.Canvas):
    """Virtual scrolling grid for photos/albums."""

    def __init__(self, parent, item_size=(150, 150), columns=5):
        super().__init__(parent)
        self.item_size = item_size
        self.columns = columns
        self.items = []  # All items (lightweight data)
        self.visible_tiles = {}  # Currently rendered tiles

        # Bind scroll event
        self.bind("<Configure>", self.on_resize)
        self.bind("<MouseWheel>", self.on_scroll)

    def on_scroll(self, event):
        """Handle scroll and update visible tiles."""
        self.yview_scroll(-1 * (event.delta // 120), "units")
        self.update_visible_tiles()

    def update_visible_tiles(self):
        """Render only visible items."""
        # Calculate visible range
        viewport_top = self.canvasy(0)
        viewport_bottom = self.canvasy(self.winfo_height())

        # Add buffer (1 screen above/below)
        buffer = self.winfo_height()
        render_top = max(0, viewport_top - buffer)
        render_bottom = viewport_bottom + buffer

        # Calculate visible row range
        row_height = self.item_size[1] + 10  # spacing
        first_row = int(render_top // row_height)
        last_row = int(render_bottom // row_height) + 1

        # Render visible items
        for row in range(first_row, last_row):
            for col in range(self.columns):
                idx = row * self.columns + col
                if idx < len(self.items) and idx not in self.visible_tiles:
                    # Create tile
                    self.visible_tiles[idx] = self.create_tile(idx)

        # Destroy off-screen tiles
        to_remove = [
            idx for idx in self.visible_tiles
            if idx // self.columns < first_row or idx // self.columns > last_row
        ]
        for idx in to_remove:
            self.visible_tiles[idx].destroy()
            del self.visible_tiles[idx]
```

### Alternatives Considered

- **Render all tiles**: Rejected; violates memory constraint (500MB limit)
- **Pagination**: Rejected; worse UX than smooth scrolling
- **Third-party grid**: Rejected; adds dependency and may not integrate with CustomTkinter

---

## 6. SQLite Schema

### Decision

Minimal schema with single `album_order` table storing user-defined album ordering. Use JSON for flexibility.

### Rationale

- **Minimal state**: Only album order needs persistence (filesystem is source of truth)
- **Simplicity**: Single table, no migrations needed for MVP
- **Flexibility**: JSON column allows adding metadata without schema changes
- **Performance**: Small dataset (<10k albums), no indexing needed

### Schema

```sql
CREATE TABLE IF NOT EXISTS album_order (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    album_path TEXT UNIQUE NOT NULL,  -- Filesystem path (unique identifier)
    sort_index INTEGER NOT NULL,      -- User-defined sort order
    metadata TEXT,                     -- JSON: {pinned: bool, custom_name: str, etc}
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sort_index ON album_order(sort_index);
```

### Access Pattern

```python
import sqlite3
import json

class AppStateDB:
    def __init__(self, db_path: Path):
        self.conn = sqlite3.connect(db_path)
        self.create_schema()

    def create_schema(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS album_order (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                album_path TEXT UNIQUE NOT NULL,
                sort_index INTEGER NOT NULL,
                metadata TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_sort_index ON album_order(sort_index)")

    def get_album_order(self) -> list[tuple[str, int]]:
        """Get all albums with their sort order."""
        cursor = self.conn.execute(
            "SELECT album_path, sort_index FROM album_order ORDER BY sort_index"
        )
        return cursor.fetchall()

    def set_album_order(self, album_path: str, sort_index: int):
        """Set album sort order."""
        self.conn.execute(
            """INSERT INTO album_order (album_path, sort_index)
               VALUES (?, ?)
               ON CONFLICT(album_path) DO UPDATE SET sort_index=?, updated_at=CURRENT_TIMESTAMP""",
            (album_path, sort_index, sort_index)
        )
        self.conn.commit()
```

### Alternatives Considered

- **JSON file**: Rejected; no ACID guarantees, corruption risk
- **Full ORM (SQLAlchemy)**: Rejected; overkill for single table, adds complexity
- **Separate tables for metadata**: Rejected; over-engineering for MVP

---

## Summary of Dependencies

### Required Libraries

```toml
[project]
dependencies = [
    "pillow>=10.0.0",           # Image processing, thumbnails
    "watchdog>=3.0.0",          # Filesystem monitoring
    "customtkinter>=5.2.0",     # Modern UI components
    "rawpy>=0.18.0",            # RAW image support (CR3, NEF, etc)
    "imagecodecs>=2023.0.0",    # HEIC codec for Pillow
    "tkinterdnd2>=0.3.0",       # Drag-drop support
    "exifread>=3.0.0",          # EXIF metadata parsing
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",            # Testing framework
    "ruff>=0.1.0",              # Linting and formatting
]
```

### System Dependencies (Linux)

- Python 3.13
- tkinter (usually bundled, may need `python3-tk` package)
- libraw (for rawpy, install via `apt install libraw-dev`)

---

## Performance Validation

### Expected Performance Characteristics

| Metric | Target | Implementation Strategy |
|--------|--------|------------------------|
| Startup time | <3s | Lazy loading; defer thumbnail generation |
| Thumbnail generation | <500ms/image | PIL optimized; cached on disk |
| UI responsiveness | <100ms | Virtual scrolling; async I/O |
| Filesystem detection | <2s | watchdog with 500ms debounce |
| Memory usage | <500MB | Virtual grid (50-100 tiles); disk cache |
| Large album (500 photos) | No lag | Virtual scrolling; progressive loading |

### Bottleneck Mitigation

1. **Thumbnail generation**: Disk caching + lazy loading
2. **Large grids**: Virtual scrolling (only render visible)
3. **Filesystem watching**: Event batching (debounce)
4. **RAW decoding**: Extract embedded preview (10-100x faster)

---

## Open Questions / Future Considerations

1. **Multi-threading**: Consider thread pool for parallel thumbnail generation (future optimization)
2. **Progressive loading**: Show placeholder → thumbnail → full quality (future UX enhancement)
3. **Thumbnail cleanup**: Add periodic cache cleanup for deleted source files (low priority)
4. **Configuration file**: Add TOML config for photo directory path, thumbnail size (future)

---

**Research Status**: ✅ Complete - All technical unknowns resolved. Ready for Phase 1 (Data Model & Contracts).
