# Tasks: Photo Album Organization Application

**Input**: Design documents from `/specs/001-build-an-application/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/app-state.schema.json

**Tests**: This feature specification does not explicitly request tests. Following pragmatic testing principles, critical file operations will be tested.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create project directory structure with src/, tests/, and data/ directories
- [ ] T002 Initialize Python 3.13 project with pyproject.toml using uv
- [ ] T003 [P] Install core dependencies: customtkinter, pillow, watchdog, rawpy, tkinterdnd2, exifread
- [ ] T004 [P] Install dev dependencies: pytest, ruff
- [ ] T005 [P] Create empty __init__.py files for all modules in src/

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T006 Create AppState class with SQLite connection in src/models/app_state.py
- [ ] T007 [P] Implement database schema initialization (album_order table) in src/models/app_state.py
- [ ] T008 [P] Implement thumbnail cache utility with SHA-256 keying in src/utils/thumbnail_cache.py
- [ ] T009 [P] Implement EXIF parser for JPEG/PNG/RAW formats in src/utils/exif_parser.py
- [ ] T010 [P] Implement file validator for album/photo names in src/utils/file_validator.py
- [ ] T011 Create Album model dataclass with date parsing in src/models/album.py
- [ ] T012 Create Photo model dataclass with format detection in src/models/photo.py
- [ ] T013 Create PhotoPair grouping class for RAW-JPEG deduplication in src/models/photo.py
- [ ] T014 Implement FilesystemScanner service for discovering albums in src/services/filesystem_scanner.py
- [ ] T015 Implement PhotoProcessor service with thumbnail generation in src/services/photo_processor.py
- [ ] T016 Implement RAW image preview extraction using rawpy in src/services/photo_processor.py
- [ ] T017 Setup FilesystemWatcher with watchdog Observer pattern in src/services/filesystem_watcher.py
- [ ] T018 Implement event debouncing (500ms) in FilesystemWatcher in src/services/filesystem_watcher.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - View Photo Albums by Date (Priority: P1) 🎯 MVP

**Goal**: Display all photo albums chronologically on the main page

**Independent Test**: Launch application with photo directory, verify albums are displayed in chronological order with thumbnails

### Critical Tests for User Story 1

**NOTE: These tests verify critical functionality (file scanning, date parsing)**

- [ ] T019 [P] [US1] Implement test for album discovery and scanning in tests/test_filesystem_scanner.py
- [ ] T020 [P] [US1] Implement test for date parsing from folder names in tests/test_filesystem_scanner.py

### Implementation for User Story 1

- [ ] T021 [P] [US1] Create VirtualGrid canvas widget for scrollable grids in src/ui/widgets/virtual_grid.py
- [ ] T022 [P] [US1] Create AlbumTile widget with thumbnail display in src/ui/widgets/album_tile.py
- [ ] T023 [US1] Implement AlbumGrid view with virtual scrolling in src/ui/album_grid.py
- [ ] T024 [US1] Implement AlbumManager service for loading albums in src/services/album_manager.py
- [ ] T025 [US1] Load and restore custom album ordering from database in src/services/album_manager.py
- [ ] T026 [US1] Implement default chronological sorting (newest to oldest) in src/services/album_manager.py
- [ ] T027 [US1] Create MainWindow with album grid display in src/ui/main_window.py
- [ ] T028 [US1] Implement application startup and initialization in src/main.py (must meet <2s startup per constitution)
- [ ] T029 [US1] Add command-line argument parsing for --photo-dir in src/main.py
- [ ] T030 [US1] Connect FilesystemWatcher to UI refresh callback in src/main.py

**Checkpoint**: At this point, User Story 1 should be fully functional - users can view all albums chronologically

---

## Phase 4: User Story 2 - Browse Photos Within an Album (Priority: P1) 🎯 MVP

**Goal**: Open albums and view photos in a tile-based grid interface with RAW-JPEG deduplication

**Independent Test**: Click on any album, verify photos display in grid, verify RAW-JPEG pairs show as single thumbnail

### Critical Tests for User Story 2

**NOTE: These tests verify critical RAW-JPEG deduplication logic**

- [ ] T031 [P] [US2] Implement test for RAW-JPEG pair detection in tests/test_photo_processor.py
- [ ] T032 [P] [US2] Implement test for embedded RAW preview extraction in tests/test_photo_processor.py

### Implementation for User Story 2

- [ ] T033 [P] [US2] Create PhotoTile widget with thumbnail display in src/ui/widgets/photo_tile.py
- [ ] T034 [P] [US2] Create Lightbox modal for full-size photo viewing in src/ui/lightbox.py
- [ ] T035 [US2] Implement PhotoGrid view with virtual scrolling in src/ui/photo_grid.py
- [ ] T036 [US2] Implement photo lazy-loading when album is opened in src/services/album_manager.py
- [ ] T037 [US2] Implement PhotoPair detection and deduplication in PhotoProcessor in src/services/photo_processor.py
- [ ] T038 [US2] Add navigation: back button from album to main page in src/ui/main_window.py
- [ ] T039 [US2] Add photo click handler to open lightbox in src/ui/photo_grid.py
- [ ] T040 [US2] Implement lightbox navigation (arrow keys, close on Escape) in src/ui/lightbox.py
- [ ] T041 [US2] Add error handling for missing/corrupted images in PhotoProcessor in src/services/photo_processor.py

**Checkpoint**: At this point, User Stories 1 AND 2 should both work - full read-only browsing experience

---

## Phase 5: User Story 3 - Reorganize Albums by Drag and Drop (Priority: P2)

**Goal**: Enable drag-and-drop reordering of albums with persistent ordering

**Independent Test**: Drag an album to a new position, verify order persists after application restart

### Implementation for User Story 3

- [ ] T042 [P] [US3] Implement TkinterDnD2 drag-drop for album tiles in src/ui/widgets/drag_drop.py
- [ ] T043 [US3] Add drag-start, drag-motion, and drag-end handlers to AlbumTile in src/ui/widgets/album_tile.py
- [ ] T044 [US3] Implement visual feedback during drag (placeholder/hover states) in src/ui/album_grid.py
- [ ] T045 [US3] Add album reorder handler in AlbumManager in src/services/album_manager.py
- [ ] T046 [US3] Implement save_ordering to persist to database in src/services/album_manager.py
- [ ] T047 [US3] Add revert-to-chronological action in AlbumGrid in src/ui/album_grid.py

**Checkpoint**: At this point, User Stories 1, 2, AND 3 should all work - albums can be reordered

---

## Phase 6: User Story 4 - Create and Rename Albums (Priority: P3)

**Goal**: Create new albums and rename existing ones with filesystem integration

**Independent Test**: Create a new album, rename it, verify filesystem directory is created/renamed

### Critical Tests for User Story 4

**NOTE: These tests verify critical file operations to prevent data loss**

- [ ] T048 [P] [US4] Implement test for album creation validation in tests/test_file_operations.py
- [ ] T049 [P] [US4] Implement test for album rename validation and atomicity in tests/test_file_operations.py

### Implementation for User Story 4

- [ ] T050 [US4] Implement create_album in AlbumManager with filesystem directory creation in src/services/album_manager.py
- [ ] T051 [US4] Implement rename_album in AlbumManager with filesystem rename in src/services/album_manager.py
- [ ] T052 [US4] Add album name validation (no invalid chars, no duplicates) in src/utils/file_validator.py
- [ ] T053 [US4] Add "Create New Album" button to AlbumGrid in src/ui/album_grid.py
- [ ] T054 [US4] Add album name edit dialog to AlbumTile (F2 key or click name) in src/ui/widgets/album_tile.py
- [ ] T055 [US4] Add error handling for invalid names and conflicts in src/ui/album_grid.py

**Checkpoint**: At this point, albums can be created and renamed with filesystem integration

---

## Phase 7: User Story 5 - Move Photos Between Albums (Priority: P3)

**Goal**: Select photos and move them between albums with filesystem operations

**Independent Test**: Select multiple photos, move to another album, verify files are moved on filesystem

### Critical Tests for User Story 5

**NOTE: These tests verify critical file move operations to prevent data loss**

- [ ] T056 [P] [US5] Implement test for photo move atomicity and rollback in tests/test_file_operations.py
- [ ] T057 [P] [US5] Implement test for RAW-JPEG pair moving together in tests/test_file_operations.py

### Implementation for User Story 5

- [ ] T058 [P] [US5] Create PhotoManager service for photo operations in src/services/photo_manager.py
- [ ] T059 [US5] Implement drag-to-select for photos in PhotoGrid in src/ui/photo_grid.py
- [ ] T060 [US5] Add selection rectangle drawing in PhotoGrid in src/ui/photo_grid.py
- [ ] T061 [US5] Add visual highlighting for selected photos in PhotoTile in src/ui/widgets/photo_tile.py
- [ ] T062 [US5] Implement move_photos in PhotoManager with filesystem operations in src/services/photo_manager.py
- [ ] T063 [US5] Ensure RAW-JPEG pairs move together in PhotoManager in src/services/photo_manager.py
- [ ] T064 [US5] Add "Move to Album" dialog/menu in PhotoGrid in src/ui/photo_grid.py
- [ ] T065 [US5] Implement atomic file moves with rollback on failure in src/services/photo_manager.py
- [ ] T066 [US5] Add UI updates for source and destination albums after move in src/ui/main_window.py

**Checkpoint**: All user stories should now be independently functional - full feature set complete

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T067 [P] Add keyboard shortcuts (Ctrl+Q quit, Escape back, F11 fullscreen) in src/ui/main_window.py
- [ ] T068 [P] Add loading indicators for long operations in src/ui/main_window.py
- [ ] T069 [P] Implement error state display for unavailable photo directory in src/ui/main_window.py
- [ ] T070 [P] Add empty state messages (empty album, no albums) in src/ui/album_grid.py and src/ui/photo_grid.py
- [ ] T071 [P] Create README.md with setup instructions and usage
- [ ] T072 Performance optimization: Profile and optimize virtual scrolling for 500+ albums
- [ ] T073 Code cleanup: Remove debug logging and add production logging configuration
- [ ] T074 Validate quickstart.md instructions by following setup steps
- [ ] T075 Add configuration file support (optional alternative to CLI args)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - User Story 1 (P1): Can start after Foundational
  - User Story 2 (P1): Can start after Foundational, integrates with US1
  - User Story 3 (P2): Can start after Foundational + US1 (needs album display)
  - User Story 4 (P3): Can start after Foundational + US1 (needs album management)
  - User Story 5 (P3): Can start after Foundational + US2 (needs photo display)
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational (Phase 2) - Integrates with US1 but independently testable
- **User Story 3 (P2)**: Requires US1 complete (needs album display to reorder)
- **User Story 4 (P3)**: Requires US1 complete (needs album display to create/rename)
- **User Story 5 (P3)**: Requires US2 complete (needs photo display to select/move)

### Within Each User Story

- Tests (if included) MUST be written and FAIL before implementation
- Models/utilities before services
- Services before UI components
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- **Setup**: T003, T004, T005 can run in parallel
- **Foundational**: T007-T010, T011-T013 can run in parallel; T019-T020 can run in parallel
- **User Story 1**: T019-T020 (tests), T021-T022 can run in parallel
- **User Story 2**: T031-T032 (tests), T033-T034 can run in parallel
- **User Story 4**: T048-T049 (tests) can run in parallel
- **User Story 5**: T056-T057 (tests), T058-T061 can run in parallel
- **Polish**: T067-T071 can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Implement test for album discovery and scanning in tests/test_filesystem_scanner.py"
Task: "Implement test for date parsing from folder names in tests/test_filesystem_scanner.py"

# Launch UI widgets in parallel:
Task: "Create VirtualGrid canvas widget for scrollable grids in src/ui/widgets/virtual_grid.py"
Task: "Create AlbumTile widget with thumbnail display in src/ui/widgets/album_tile.py"
```

## Parallel Example: Foundational Phase

```bash
# Launch all utilities in parallel:
Task: "Implement database schema initialization (album_order table) in src/models/app_state.py"
Task: "Implement thumbnail cache utility with SHA-256 keying in src/utils/thumbnail_cache.py"
Task: "Implement EXIF parser for JPEG/PNG/RAW formats in src/utils/exif_parser.py"
Task: "Implement file validator for album/photo names in src/utils/file_validator.py"

# Launch all models in parallel:
Task: "Create Album model dataclass with date parsing in src/models/album.py"
Task: "Create Photo model dataclass with format detection in src/models/photo.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 Only)

1. Complete Phase 1: Setup (T001-T005)
2. Complete Phase 2: Foundational (T006-T018) - CRITICAL - blocks all stories
3. Complete Phase 3: User Story 1 (T019-T030)
4. Complete Phase 4: User Story 2 (T031-T041)
5. **STOP and VALIDATE**: Test read-only browsing experience independently
6. Deploy/demo if ready - this is the MVP!

### Incremental Delivery

1. **Foundation** (Setup + Foundational) → Core infrastructure ready
2. **MVP** (US1 + US2) → Test independently → Deploy/Demo (Read-only album and photo browsing)
3. **Enhanced** (US3) → Test independently → Deploy/Demo (Add album reordering)
4. **Full Feature** (US4 + US5) → Test independently → Deploy/Demo (Add album/photo management)
5. **Polish** (Phase 8) → Final cleanup and optimization

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (T001-T018)
2. Once Foundational is done:
   - Developer A: User Story 1 (T019-T030)
   - Developer B: User Story 2 (T031-T041) - starts after US1 has AlbumManager ready
   - Developer C: Begin User Story 3 (T042-T047) once US1 is complete
3. Stories complete and integrate independently
4. After US1+US2 (MVP), can deploy while continuing with US3-US5

---

## Task Breakdown Summary

**Total Tasks**: 75

### By Phase:
- **Phase 1 (Setup)**: 5 tasks
- **Phase 2 (Foundational)**: 13 tasks (BLOCKS all stories)
- **Phase 3 (User Story 1 - P1)**: 12 tasks (MVP)
- **Phase 4 (User Story 2 - P1)**: 11 tasks (MVP)
- **Phase 5 (User Story 3 - P2)**: 6 tasks
- **Phase 6 (User Story 4 - P3)**: 8 tasks
- **Phase 7 (User Story 5 - P3)**: 11 tasks
- **Phase 8 (Polish)**: 9 tasks

### By Priority:
- **Critical Path (Setup + Foundational)**: 18 tasks (23.1%)
- **MVP (US1 + US2)**: 23 tasks (30.7%)
- **Enhanced (US3)**: 6 tasks (8.0%)
- **Full Feature (US4 + US5)**: 19 tasks (25.3%)
- **Polish**: 9 tasks (12.0%)

### Parallel Opportunities:
- **32 tasks** marked [P] can run in parallel with others in same phase (42.7%)
- **5 user stories** can be worked on independently after foundational phase

### Independent Test Criteria:
- **User Story 1**: Launch app → See albums in chronological order → All albums visible
- **User Story 2**: Click album → See photos in grid → RAW-JPEG shown as one thumbnail → Click photo → Lightbox opens
- **User Story 3**: Drag album → Drop in new position → Restart app → Order persists
- **User Story 4**: Create album → Rename album → Verify filesystem directory created/renamed
- **User Story 5**: Select photos → Move to album → Verify files moved on filesystem

### Suggested MVP Scope:
**Phase 1 + Phase 2 + Phase 3 + Phase 4** (41 tasks, 54.7% of total)
- Delivers: Full read-only photo album browsing experience
- Users can: View all albums chronologically, browse photos within albums, see full-size photos, benefit from RAW-JPEG deduplication
- Missing: Album reordering, album creation/renaming, photo moving (all non-critical for initial value)

---

## Notes

- [P] tasks = different files, no dependencies, can run in parallel
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (TDD for critical operations)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Performance targets: <3s startup, <2s thumbnail load, <2s filesystem detection, <500MB memory
- Critical file operations have tests to prevent data loss (album rename, photo move, RAW-JPEG pairing)
