# Implementation Plan: Photo Album Organization Application

**Branch**: `001-build-an-application` | **Date**: 2025-10-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-build-an-application/spec.md`

## Summary

A Python 3.13 desktop application for organizing photo albums from a local filesystem directory. The application provides a tile-based UI for viewing albums chronologically, browsing photos within albums, and reorganizing collections through drag-and-drop. Key features include RAW-JPEG deduplication, lightbox photo viewing, filesystem watching for external changes, and destructive filesystem operations (moving/renaming files directly).

**Technical Approach**: tkinter-based desktop GUI with CustomTkinter for modern components, PIL for image processing, watchdog for filesystem monitoring, and local JSON/SQLite for persistent state (album ordering).

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: tkinter (stdlib), CustomTkinter, Pillow (PIL), watchdog, exifread
**Storage**: SQLite for application state (album ordering), filesystem as source of truth for albums/photos
**Testing**: pytest (minimal, pragmatic testing per constitution)
**Target Platform**: Linux desktop (Ubuntu/Debian-based systems)
**Project Type**: Single desktop application
**Performance Goals**: <2s startup, <2s thumbnail loading, <2s filesystem change detection, 500 photo albums without lag
**Constraints**: <100ms UI response, <500MB memory usage, handles 50,000+ photos
**Scale/Scope**: Single-user desktop app, ~10-15 screens/views, local filesystem operations only

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Principle I: Code Quality & Simplicity ✅

- **Pass**: Single Python application with standard structure, minimal dependencies (tkinter, PIL, watchdog)
- **Pass**: No complex abstractions required; straightforward MVC pattern for desktop GUI
- **Pass**: Using standard library (tkinter) and well-established libraries (PIL for images)

### Principle II: User Experience Consistency ✅

- **Pass**: Spec defines consistent interaction patterns (drag-drop for albums and photo selection)
- **Pass**: Consistent navigation (back button, lightbox close)
- **Pass**: Error handling specified for missing/corrupted files
- **Pass**: File operations are predictable (destructive filesystem changes clearly defined)

### Principle III: Performance First ✅

- **Pass**: Performance requirements clearly defined in success criteria (SC-001 through SC-011)
- **Pass**: Lazy loading specified for thumbnails (FR-005)
- **Pass**: Async filesystem watching specified (FR-001a, SC-011: 2s detection)
- **Pass**: Bounded memory through streaming/lazy loading design
- **Pass**: Progressive rendering planned for large albums

### Principle IV: Pragmatic Testing ⚠️

- **Note**: Minimal testing approach; focus on critical file operations
- **Tests planned for**: File move operations (data loss risk), RAW-JPEG deduplication logic (complex algorithm), filesystem validation (corruption risk)
- **Manual testing**: UI workflows, drag-drop interactions, lightbox behavior

### Principle V: Progressive Enhancement ✅

- **Pass**: Spec includes prioritized user stories (P1: view albums/photos, P2: reorder, P3: create/rename/move)
- **Pass**: P1 stories are independently deployable MVP (read-only album browsing)
- **Pass**: Each story is independently testable per spec

**Gate Status**: ✅ PASSED - Proceed to Phase 0 Research

## Project Structure

### Documentation (this feature)

```
specs/001-build-an-application/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (CLI interface contracts)
│   └── app-state.schema.json
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```
src/
├── models/              # Data models (Album, Photo, AppState)
│   ├── __init__.py
│   ├── album.py
│   ├── photo.py
│   └── app_state.py
├── services/            # Business logic
│   ├── __init__.py
│   ├── filesystem_scanner.py      # Scan directories for albums
│   ├── filesystem_watcher.py      # Watch for external changes
│   ├── photo_processor.py         # Thumbnail generation, deduplication
│   ├── album_manager.py           # Album CRUD operations
│   └── photo_manager.py           # Photo operations (move, select)
├── ui/                  # User interface components
│   ├── __init__.py
│   ├── main_window.py             # Main application window
│   ├── album_grid.py              # Album tiles grid view
│   ├── photo_grid.py              # Photo tiles grid view
│   ├── lightbox.py                # Full-size photo modal
│   └── widgets/
│       ├── album_tile.py          # Individual album tile
│       ├── photo_tile.py          # Individual photo tile
│       └── drag_drop.py           # Drag-drop helpers
├── utils/               # Utilities
│   ├── __init__.py
│   ├── exif_parser.py             # EXIF metadata extraction
│   ├── file_validator.py          # Filename validation
│   └── thumbnail_cache.py         # Thumbnail caching
└── main.py              # Application entry point

tests/
├── test_photo_processor.py        # RAW-JPEG deduplication tests
├── test_file_operations.py        # File move/rename safety tests
└── test_filesystem_scanner.py     # Album discovery tests

data/
├── thumbnails/          # Generated thumbnail cache
└── app.db              # SQLite database for app state

pyproject.toml           # uv project configuration
README.md               # Setup and usage instructions
```

**Structure Decision**: Single desktop application structure selected. Python package in `src/` directory with clear separation of concerns (models, services, UI). Uses standard MVC-like pattern suitable for tkinter applications. Test directory focuses on critical file operations per pragmatic testing principle.

## Complexity Tracking

*No constitution violations requiring justification.*

All dependencies are standard, well-established libraries:

- tkinter: Python standard library
- CustomTkinter: Modern tkinter wrapper for better UI components
- Pillow: Industry-standard image processing
- watchdog: Standard filesystem monitoring library
- exifread: Lightweight EXIF parsing

No complex abstractions required beyond standard service/model separation.

## Phase 0: Research & Unknowns

Research tasks to resolve before design:

1. **Thumbnail Generation Strategy**: Best practices for PIL thumbnail creation with caching
2. **Filesystem Watching**: watchdog library patterns for efficient directory monitoring on Linux
3. **RAW Image Support**: PIL/Pillow support for CR3, HEIC formats (may need rawpy library)
4. **Drag-Drop in tkinter**: CustomTkinter or tkinter DND implementation patterns
5. **Large Grid Performance**: Virtualization/windowing strategies for 500+ items in tkinter grid
6. **SQLite Schema**: Minimal schema for persisting album ordering

Output: `research.md` with decisions, rationale, and code examples for each area.

## Phase 1: Design & Contracts

After research completion:

1. **Data Model** (`data-model.md`):
   - Album entity with filesystem path, display name, date, sort order
   - Photo entity with path, format, thumbnail path, EXIF data
   - PhotoPair grouping for RAW-JPEG deduplication
   - AppState for persisted ordering

2. **Contracts** (`contracts/`):
   - `app-state.schema.json`: SQLite schema for app state
   - Internal API contracts between UI and services (Python type hints)

3. **Quickstart Guide** (`quickstart.md`):
   - Development setup with uv
   - Running the application
   - Project structure walkthrough
   - Configuration (photo directory path)

4. **Agent Context Update**: Add Python 3.13, tkinter, CustomTkinter, PIL, watchdog to agent memory

## Post-Design Constitution Check

*Re-evaluation after Phase 1 design completion*

### Principle I: Code Quality & Simplicity ✅

- **Pass**: Data model uses simple dataclasses, no complex ORM
- **Pass**: Service layer has clear separation of concerns (scanner, watcher, processor, managers)
- **Pass**: UI components follow standard tkinter patterns
- **Confirmed**: Minimal dependencies, all well-established libraries

### Principle II: User Experience Consistency ✅

- **Pass**: Consistent interaction patterns defined (drag-drop for both albums and photos)
- **Pass**: Standard navigation (back button, Escape key, lightbox close)
- **Pass**: Consistent error handling in file operations contract
- **Pass**: Keyboard shortcuts defined for all major actions

### Principle III: Performance First ✅

- **Pass**: Virtual scrolling design for large grids (meets SC-006)
- **Pass**: Lazy loading strategy for photos and EXIF data
- **Pass**: Disk-based thumbnail caching with bounded memory
- **Pass**: Filesystem watcher with debouncing (500ms) meets SC-011
- **Pass**: RAW preview extraction (10-100x faster than full decode)

### Principle IV: Pragmatic Testing ✅

- **Pass**: Tests focused on critical operations (file moves, deduplication, scanning)
- **Pass**: Manual testing plan for UI interactions
- **Pass**: No excessive test coverage requirements

### Principle V: Progressive Enhancement ✅

- **Pass**: P1 (view albums/photos) is deployable MVP without P2/P3 features
- **Pass**: Each user story independently implementable
- **Pass**: Design supports incremental feature addition

**Final Gate Status**: ✅ PASSED - Design adheres to all constitutional principles

## Artifacts Generated

### Phase 0: Research (Complete)

- ✅ `research.md`: Technical decisions for 6 key areas
  - Thumbnail generation (PIL with disk caching)
  - Filesystem watching (watchdog with debouncing)
  - RAW image support (rawpy with preview extraction)
  - Drag-drop (TkinterDnD2 for albums, custom for photo selection)
  - Grid performance (virtual scrolling)
  - Database schema (minimal SQLite)

### Phase 1: Design & Contracts (Complete)

- ✅ `data-model.md`: 5 core entities with relationships and validation
  - AppState, Album, Photo, PhotoPair, AlbumOrder
  - State machines and lifecycle diagrams
  - Performance considerations
- ✅ `contracts/app-state.schema.json`: Database schema and API contracts
  - SQLite table definitions
  - Python type contracts
  - UI event contracts
  - File operation contracts
- ✅ `quickstart.md`: Developer onboarding guide
  - Setup instructions
  - Project structure walkthrough
  - Configuration guide
  - Keyboard shortcuts
  - Troubleshooting
- ✅ Agent context updated: CLAUDE.md with Python 3.13 + tech stack

## Next Steps

**Ready for implementation!** Run `/speckit.tasks` to generate prioritized implementation tasks.

The generated tasks will break down the 5 user stories into:

- P1 Tasks: View albums & browse photos (MVP)
- P2 Tasks: Drag-drop album reordering
- P3 Tasks: Create/rename albums, move photos

**Note**: This plan stops at Phase 1 completion per `/speckit.plan` specification. Task generation is a separate command (`/speckit.tasks`).
