# Data Model: Photo Album Organization Application

**Date**: 2025-10-15
**Updated**: 2025-10-16 (Changed UI framework from tkinter/CustomTkinter to PyQt6)
**Status**: Complete

This document defines the core data entities and their relationships for the photo album organization application.

## Entity Diagram

```
┌─────────────────┐
│   AppState      │
│─────────────────│
│ photo_dir: Path │
│ db_conn: SQLite │
└────────┬────────┘
         │
         │ manages
         ├─────────────────────────────┐
         │                             │
         ▼                             ▼
┌─────────────────┐           ┌─────────────────┐
│     Album       │           │  AlbumOrder     │
│─────────────────│           │─────────────────│
│ path: Path      │───────────│ album_path: str │
│ name: str       │  1:1      │ sort_index: int │
│ date: date|None │           │ metadata: dict  │
│ photo_count: int│           └─────────────────┘
└────────┬────────┘
         │
         │ contains
         │ 1:N
         ▼
┌─────────────────┐           ┌─────────────────┐
│     Photo       │           │   PhotoPair     │
│─────────────────│  grouped  │─────────────────│
│ path: Path      │───────────│ base_name: str  │
│ filename: str   │    by     │ raw_path: Path? │
│ format: str     │           │ jpeg_path: Path │
│ size: int       │           └─────────────────┘
│ thumbnail: Path?│
│ exif_date: date?│
└─────────────────┘
```

## Core Entities

### 1. AppState

**Purpose**: Central application state managing the photo directory, database connection, and loaded albums.

**Attributes**:
- `photo_dir: Path` - Root directory containing photo albums
- `state_file: Path` - Path to JSON state file (default: data/app_state.json)
- `thumbnail_cache_dir: Path` - Directory for cached thumbnails
- `albums: list[Album]` - Currently loaded albums
- `current_view: str` - Current view state ("albums" | "album_detail" | "lightbox")

**Responsibilities**:
- Load and save application state from JSON file
- Scan photo directory and load albums
- Coordinate between filesystem and UI state
- Persist and restore album ordering

**Lifecycle**:
1. Created on application startup
2. Loads albums from filesystem
3. Restores custom ordering from database
4. Updates in response to filesystem changes
5. Saves state on shutdown

**Validation Rules**:
- `photo_dir` MUST exist and be readable
- `thumbnail_cache_dir` MUST be writable
- `state_file` parent directory MUST be writable
- JSON state file MUST be valid JSON (or missing, for fresh start)

---

### 2. Album

**Purpose**: Represents a photo album corresponding to a filesystem directory.

**Attributes**:
- `path: Path` - Absolute path to album directory
- `name: str` - Display name (directory name or custom name)
- `date: datetime.date | None` - Parsed date from folder name or None
- `photo_count: int` - Number of photos in album (cached)
- `thumbnail_path: Path | None` - Path to preview thumbnail
- `photos: list[Photo]` - Lazy-loaded list of photos

**Derived Properties**:
- `display_name: str` - Formatted name for UI display
- `date_string: str` - Formatted date string or "Unknown Date"

**Responsibilities**:
- Parse date from folder name (format: YYYY-MM-DD or YYYY-MM-DD_Description)
- Lazy-load photos when accessed
- Generate preview thumbnail (first photo in album)
- Track metadata for sorting

**Lifecycle**:
1. Created when directory is discovered by filesystem scanner
2. Photos loaded lazily when album is opened
3. Updated when filesystem changes are detected
4. Removed when directory is deleted

**Validation Rules**:
- `path` MUST exist and be a directory
- `name` MUST NOT be empty
- `name` MUST NOT contain filesystem-invalid characters: / \ : * ? " < > |
- `photo_count` MUST be >= 0

**Date Parsing Logic**:
```python
def parse_date_from_name(name: str) -> datetime.date | None:
    """Extract date from folder name like '2022-12-08_Paris' or '2022-12-08'."""
    match = re.match(r'^(\d{4})-(\d{2})-(\d{2})', name)
    if match:
        year, month, day = map(int, match.groups())
        try:
            return datetime.date(year, month, day)
        except ValueError:
            return None
    return None
```

---

### 3. Photo

**Purpose**: Represents an individual photo file.

**Attributes**:
- `path: Path` - Absolute path to photo file
- `filename: str` - File name with extension
- `format: str` - File format/extension (lowercase): "jpg", "cr3", "png", "heic"
- `size_bytes: int` - File size in bytes
- `thumbnail_path: Path | None` - Path to cached thumbnail
- `exif_date: datetime.datetime | None` - Date from EXIF data
- `width: int | None` - Image width in pixels (from EXIF or lazy-loaded)
- `height: int | None` - Image height in pixels

**Derived Properties**:
- `display_date: datetime.datetime` - EXIF date or file modification time
- `is_raw: bool` - True if format is RAW (cr3, nef, arw, dng)
- `base_name: str` - Filename without extension (for pairing detection)

**Responsibilities**:
- Load EXIF metadata on-demand
- Generate and cache thumbnail
- Provide display-ready metadata

**Lifecycle**:
1. Created when file is discovered during album scan
2. EXIF loaded lazily when needed
3. Thumbnail generated on first display
4. Updated when file is modified
5. Removed when file is deleted

**Validation Rules**:
- `path` MUST exist and be a file
- `format` MUST be in supported formats: jpg, jpeg, png, heic, cr3, nef, arw, dng
- `size_bytes` MUST be > 0 for valid files

**EXIF Parsing**:
```python
def load_exif(self) -> dict:
    """Load EXIF metadata from photo file."""
    if self.format in ['cr3', 'nef', 'arw', 'dng']:
        # RAW format - use rawpy
        with rawpy.imread(str(self.path)) as raw:
            return raw.metadata
    else:
        # Standard format - use exifread
        with open(self.path, 'rb') as f:
            tags = exifread.process_file(f)
            return {k: str(v) for k, v in tags.items()}
```

---

### 4. PhotoPair

**Purpose**: Groups RAW and JPEG versions of the same photo for deduplication.

**Attributes**:
- `base_name: str` - Common filename without extension (e.g., "IMG_6783")
- `raw_path: Path | None` - Path to RAW file (.cr3, .nef, etc.)
- `jpeg_path: Path` - Path to JPEG file (.jpg, .jpeg)

**Derived Properties**:
- `display_path: Path` - JPEG path (preferred for display)
- `has_raw: bool` - True if RAW version exists

**Responsibilities**:
- Detect and group RAW-JPEG pairs
- Provide single logical photo for UI display
- Track both versions for file operations

**Lifecycle**:
1. Created during photo loading if matching RAW-JPEG pair detected
2. Used for deduplication in photo grid display
3. Both files moved together during photo move operations

**Pairing Logic**:
```python
def detect_pairs(photos: list[Photo]) -> list[PhotoPair]:
    """Group photos by base name to detect RAW-JPEG pairs."""
    pairs = {}

    for photo in photos:
        base = photo.base_name
        if base not in pairs:
            pairs[base] = {'raw': None, 'jpeg': None}

        if photo.is_raw:
            pairs[base]['raw'] = photo.path
        else:
            pairs[base]['jpeg'] = photo.path

    # Create PhotoPair objects for matches
    result = []
    for base, paths in pairs.items():
        if paths['jpeg']:  # JPEG required
            result.append(PhotoPair(
                base_name=base,
                raw_path=paths['raw'],
                jpeg_path=paths['jpeg']
            ))

    return result
```

---

### 5. AlbumOrder (JSON File)

**Purpose**: Persists user-defined album ordering in a JSON file.

**File Location**: `data/app_state.json`

**Schema**:
```json
{
  "version": "1.0",
  "album_order": [
    {
      "album_path": "/absolute/path/to/album1",
      "sort_index": 0,
      "metadata": {
        "pinned": false,
        "custom_name": null,
        "color_tag": null
      },
      "updated_at": "2025-10-15T14:30:00Z"
    },
    {
      "album_path": "/absolute/path/to/album2",
      "sort_index": 1,
      "metadata": {},
      "updated_at": "2025-10-15T14:35:00Z"
    }
  ]
}
```

**Structure**:
- `version: str` - Schema version for future migrations
- `album_order: list[dict]` - Ordered list of album configurations
  - `album_path: str` - Filesystem path (unique identifier)
  - `sort_index: int` - User-defined sort position (0-based)
  - `metadata: dict` - Optional metadata fields
  - `updated_at: str` - ISO 8601 timestamp

**Metadata Fields** (optional):
- `pinned: bool` - Whether album is pinned to top
- `custom_name: str | null` - Custom display name
- `color_tag: str | null` - Color tag for grouping

**Responsibilities**:
- Persist custom album ordering across sessions
- Support future metadata extension without schema changes
- Simple file format for easy inspection and debugging

**File Operations**:
```python
import json
from pathlib import Path
from datetime import datetime

def load_album_order(state_file: Path) -> list[dict]:
    """Load album order from JSON file."""
    if not state_file.exists():
        return []
    with open(state_file, 'r') as f:
        data = json.load(f)
        return data.get('album_order', [])

def save_album_order(state_file: Path, album_order: list[dict]):
    """Save album order to JSON file."""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    data = {
        'version': '1.0',
        'album_order': album_order
    }
    with open(state_file, 'w') as f:
        json.dump(data, f, indent=2)
```

---

## Relationships

### Album → Photo (1:N)
- One album contains many photos
- Photos are discovered by scanning album directory
- Relationship is implicit (filesystem-based)

### Photo → PhotoPair (N:1)
- Multiple photos (RAW + JPEG) may form one PhotoPair
- Grouping is based on base filename matching
- Optional relationship (not all photos have pairs)

### AppState → Album (1:N)
- AppState manages collection of all albums
- Albums are loaded from filesystem on startup
- Ordering is restored from AlbumOrder database

### Album → AlbumOrder (1:1)
- Each album may have custom sort order in database
- Relationship is optional (albums without custom order use default chronological)

---

## State Transitions

### Album State Machine

```
┌─────────────┐
│ Discovered  │ (directory found by scanner)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Loaded    │ (metadata parsed, preview generated)
└──────┬──────┘
       │
       ├──────────────┐
       │              ▼
       │       ┌─────────────┐
       │       │   Opening   │ (photos being loaded)
       │       └──────┬──────┘
       │              │
       │              ▼
       │       ┌─────────────┐
       │       │   Opened    │ (photos loaded and displayed)
       │       └──────┬──────┘
       │              │
       └──────────────┘
```

### Photo Selection State

```
┌─────────────┐
│ Unselected  │
└──────┬──────┘
       │ (drag-to-select)
       ▼
┌─────────────┐
│  Selected   │
└──────┬──────┘
       │ (move/deselect)
       ▼
┌─────────────┐
│ Unselected  │
└─────────────┘
```

---

## Validation Summary

### Critical Validations (Prevent Data Loss)

1. **Album rename**: Validate no duplicate names, no invalid characters
2. **Photo move**: Validate destination exists, source files exist, no name conflicts
3. **File operations**: Atomic operations with rollback on failure

### Non-Critical Validations (UX)

1. **Date parsing**: Gracefully handle invalid dates (show "Unknown Date")
2. **Missing thumbnails**: Generate on-demand if cache entry missing
3. **Corrupted files**: Show placeholder, log error, continue loading others

---

## Performance Considerations

### Lazy Loading
- Photos loaded only when album is opened (not on startup)
- EXIF data extracted on-demand
- Thumbnails generated on first view

### Caching Strategy
- Thumbnail cache: Disk-based, keyed by SHA-256 of source path
- EXIF cache: In-memory, invalidated when file modified
- Album metadata: Cached in AppState, refreshed on filesystem changes

### Memory Bounds
- Maximum loaded albums: Unlimited (metadata only, ~1KB each)
- Maximum loaded photos: Limited by virtual scrolling (~100 at a time)
- Thumbnail cache: Disk-based, no memory constraint

---

**Data Model Status**: ✅ Complete - Ready for implementation.
