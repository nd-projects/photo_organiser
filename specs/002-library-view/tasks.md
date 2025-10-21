# Tasks: Library View

**Input**: Design documents from `/specs/002-library-view/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/library_view_api.py

**Tests**: Not explicitly requested in spec - manual testing preferred per constitution

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- Single desktop application: `src/`, `tests/` at repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Verify existing project structure matches plan.md requirements
- [X] T002 [P] Verify directory structure exists: src/models/, src/services/, src/utils/ (create if missing)
- [X] T003 [P] Verify UI directory structure exists: src/ui/ and src/ui/widgets/ (create if missing)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Create LibraryItem dataclass in src/models/library_item.py with all fields from data-model.md
- [X] T005 [P] Create ViewGroup entities (DayGroup, MonthGroup, YearGroup, EventCluster) in src/models/view_groups.py
- [X] T006 Create LibraryService class skeleton in src/services/library_service.py implementing ILibraryService interface
- [X] T007 Implement LibraryService.load_library() method to scan filesystem, extract EXIF metadata using ExifParser, and create LibraryItem objects
- [X] T008 [P] Create ThumbnailLoader class in src/utils/async_loader.py with QThreadPool-based worker pattern
- [X] T009 [P] Modify ThumbnailCache in src/utils/thumbnail_cache.py to add mtime-based cache invalidation logic
- [X] T010 Create PhotoLibraryModel (QAbstractListModel) in src/ui/widgets/virtual_grid.py with lazy loading support
- [X] T011 Create ThumbnailDelegate (QStyledItemDelegate) in src/ui/widgets/virtual_grid.py with async thumbnail loading
- [X] T012 Create VirtualGridWidget (QListView) in src/ui/widgets/virtual_grid.py with IconMode and uniformItemSizes configuration

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - View All Photos in Grid (Priority: P1) 🎯 MVP

**Goal**: Scrollable grid of all photos with async thumbnail loading, supporting 10,000+ photos at 60fps

**Independent Test**: Open Library tab, select "All Photos", verify all photos display in scrollable grid with progressive thumbnail loading

### Implementation for User Story 1

- [X] T013 [US1] Implement LibraryService.get_all_items(offset, limit) method for paginated access in src/services/library_service.py
- [X] T014 [US1] Implement LibraryService.get_total_count() method in src/services/library_service.py
- [X] T015 [US1] Implement PhotoLibraryModel.rowCount() to return loaded count in src/ui/widgets/virtual_grid.py
- [X] T016 [US1] Implement PhotoLibraryModel.data() to return item data on-demand in src/ui/widgets/virtual_grid.py
- [X] T017 [US1] Implement PhotoLibraryModel.canFetchMore() and fetchMore() for lazy loading in src/ui/widgets/virtual_grid.py
- [X] T018 [US1] Implement ThumbnailDelegate.paint() with placeholder and async load triggering in src/ui/widgets/virtual_grid.py
- [X] T019 [US1] Implement ThumbnailDelegate.sizeHint() with uniform size in src/ui/widgets/virtual_grid.py
- [X] T020 [US1] Implement ThumbnailWorker (QRunnable) for background thumbnail loading in src/utils/async_loader.py
- [X] T021 [US1] Implement ThumbnailLoader signal connections and queue management in src/utils/async_loader.py
- [X] T022 [US1] Create AllPhotosGrid widget in src/ui/all_photos_grid.py integrating VirtualGridWidget with LibraryService
- [X] T023 [US1] Connect ThumbnailDelegate.thumbnail_requested signal to ThumbnailLoader in src/ui/all_photos_grid.py
- [X] T024 [US1] Connect ThumbnailLoader.thumbnail_ready signal to update delegate cache in src/ui/all_photos_grid.py
- [X] T025 [US1] Create LibraryView container widget in src/ui/library_view.py with tab navigation for view modes
- [X] T026 [US1] Add AllPhotosGrid to LibraryView as default view in src/ui/library_view.py
- [X] T027 [US1] Modify MainWindow in src/ui/main_window.py to add Library tab with LibraryView widget
- [X] T028 [US1] Initialize LibraryService and load library on MainWindow startup in src/ui/main_window.py
- [X] T029 [US1] Add error handling for failed thumbnails (placeholder with error icon) in src/ui/widgets/virtual_grid.py
- [X] T030 [US1] Add video detection and play icon overlay in ThumbnailDelegate.paint() in src/ui/widgets/virtual_grid.py
- [X] T031 [US1] Implement LRU cache eviction (max 500 QPixmaps) in ThumbnailDelegate in src/ui/widgets/virtual_grid.py

**Checkpoint**: At this point, User Story 1 should be fully functional - can view entire library in scrollable grid with smooth 60fps performance

**Manual Testing for US1**:

- Launch app with 1,000+ photos
- Click Library tab
- Verify grid displays with smooth scrolling
- Verify thumbnails load progressively
- Verify videos show play icon
- Test rapid scrolling (Page Down)
- Monitor memory usage stays <500MB

---

## Phase 4: User Story 2 - Browse Photos by Days (Priority: P2)

**Goal**: Organize photos chronologically by day with best shots highlighted using EXIF quality metrics

**Independent Test**: Navigate to Days view, verify photos grouped by day with top 5 best shots per day highlighted

### Implementation for User Story 2

- [X] T032 [US2] Create PhotoQualityRanker class in src/services/photo_quality.py implementing IPhotoQualityRanker interface
- [X] T033 [US2] Implement _score_iso() helper function for ISO quality scoring in src/services/photo_quality.py
- [X] T034 [US2] Implement _score_camera_shake() helper function using reciprocal rule in src/services/photo_quality.py
- [X] T035 [US2] Implement _score_aperture() helper function for optimal aperture range in src/services/photo_quality.py
- [X] T036 [US2] Implement _score_exposure_comp() helper function in src/services/photo_quality.py
- [X] T037 [US2] Implement _score_flash() helper function in src/services/photo_quality.py
- [X] T038 [US2] Implement PhotoQualityRanker.calculate_score() with weighted combination in src/services/photo_quality.py
- [X] T039 [US2] Implement PhotoQualityRanker.select_best_shots() to return top N by quality in src/services/photo_quality.py
- [X] T040 [US2] Modify LibraryService.load_library() to compute quality_score for each LibraryItem in src/services/library_service.py
- [X] T041 [US2] Implement LibraryService._group_items_by_date() helper method in src/services/library_service.py
- [X] T042 [US2] Implement LibraryService.get_days(year, month) method to return DayGroup list in src/services/library_service.py
- [X] T043 [US2] Create DaysView widget in src/ui/days_view.py with scrollable day sections
- [X] T044 [US2] Implement DaysView._create_day_section() to render day header and photos in src/ui/days_view.py
- [X] T045 [US2] Implement DaysView._create_best_shots_grid() to highlight best shots in src/ui/days_view.py
- [X] T046 [US2] Add DaysView to LibraryView tab navigation in src/ui/library_view.py
- [X] T047 [US2] Implement view switching with <500ms performance in src/ui/library_view.py
- [X] T048 [US2] Skip days without photos (only show days with content) in src/ui/days_view.py

**Checkpoint**: At this point, User Stories 1 AND 2 should both work - can view all photos grid OR browse by days with best shots

**Manual Testing for US2**:

- Navigate to Days view
- Verify photos grouped by day chronologically
- Verify best shots (top 5) highlighted per day
- Verify days without photos are skipped
- Verify view switching <500ms

---

## Phase 5: User Story 3 - Browse Photos by Months (Priority: P3)

**Goal**: Organize photos by month with significant events identified through time-based clustering

**Independent Test**: Navigate to Months view, verify photos grouped by month with events clustered by time proximity

### Implementation for User Story 3

- [ ] T049 [US3] Create EventClusterer class in src/services/event_clustering.py implementing IEventClusterer interface
- [ ] T050 [US3] Implement EventClusterer._create_event_cluster() helper function in src/services/event_clustering.py
- [ ] T051 [US3] Implement EventClusterer.cluster_by_time_gaps() with O(n) gap-based algorithm in src/services/event_clustering.py
- [ ] T052 [US3] Implement EventClusterer.cluster_by_date_boundaries() with midnight boundary support in src/services/event_clustering.py
- [ ] T053 [US3] Implement LibraryService._group_items_by_month() helper method in src/services/library_service.py
- [ ] T054 [US3] Implement LibraryService.get_months(year) method to return MonthGroup list with events in src/services/library_service.py
- [ ] T055 [US3] Create MonthsView widget in src/ui/months_view.py with scrollable month sections
- [ ] T056 [US3] Implement MonthsView._create_month_section() to render month header and events in src/ui/months_view.py
- [ ] T057 [US3] Implement MonthsView._create_event_cluster_grid() to display event photos in src/ui/months_view.py
- [ ] T058 [US3] Add MonthsView to LibraryView tab navigation in src/ui/library_view.py

**Checkpoint**: All three views (All Photos, Days, Months) should now be independently functional

**Manual Testing for US3**:

- Navigate to Months view
- Verify photos grouped by month
- Verify events clustered within months
- Verify smooth scrolling and performance

---

## Phase 6: User Story 4 - Browse Best Photos by Years (Priority: P4)

**Goal**: Display highlights from each year with temporal variety (20-50 photos per year spread across months)

**Independent Test**: Navigate to Years view, verify photos grouped by year with 20-50 highlights showing variety across the year

### Implementation for User Story 4

- [ ] T059 [US4] Implement PhotoQualityRanker.select_highlights_with_variety() for temporal distribution in src/services/photo_quality.py
- [ ] T060 [US4] Implement LibraryService._group_items_by_year() helper method in src/services/library_service.py
- [ ] T061 [US4] Implement LibraryService.get_years() method to return YearGroup list with highlights in src/services/library_service.py
- [ ] T062 [US4] Create YearsView widget in src/ui/years_view.py with scrollable year sections
- [ ] T063 [US4] Implement YearsView._create_year_section() to render year header and highlights in src/ui/years_view.py
- [ ] T064 [US4] Implement YearsView._create_highlights_grid() to display yearly highlights in src/ui/years_view.py
- [ ] T065 [US4] Add YearsView to LibraryView tab navigation in src/ui/library_view.py

**Checkpoint**: All four view modes should now be fully functional and independently testable

**Manual Testing for US4**:

- Navigate to Years view
- Verify photos grouped by year (reverse chronological)
- Verify 20-50 highlights per year
- Verify highlights spread across months

---

## Phase 7: Integration & Polish

**Purpose**: Cross-cutting concerns and improvements affecting multiple user stories

- [ ] T066 [P] Implement FilesystemWatcher integration for auto-refresh in src/services/library_service.py
- [ ] T067 [P] Implement LibraryService.refresh() method for auto-refresh on file changes in src/services/library_service.py
- [ ] T068 Connect FilesystemWatcher signals to LibraryService.refresh() in src/ui/main_window.py
- [ ] T069 [P] Add error logging for thumbnail generation failures in src/utils/async_loader.py
- [ ] T070 [P] Add error logging for EXIF extraction failures in src/services/library_service.py
- [ ] T071 [P] Add graceful handling of photos without EXIF dates (use file mtime) in src/services/library_service.py
- [ ] T072 [P] Add video duration extraction using Pillow/rawpy in src/services/library_service.py
- [ ] T073 Verify performance with 10,000 photos (60fps scrolling, <2s thumbnail load per viewport)
- [ ] T074 Verify performance with 50,000 photos (memory <500MB, no degradation)
- [ ] T075 Verify view switching performance (<500ms) across all four views
- [ ] T076 [P] Run quickstart.md validation with test photo library
- [ ] T077 [P] Test cache invalidation when source files modified

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - User stories CAN proceed in parallel if team capacity allows
  - OR sequentially in priority order (P1 → P2 → P3 → P4)
- **Integration & Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Extends US1 but independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Extends US1 but independently testable
- **User Story 4 (P4)**: Can start after Foundational (Phase 2) - Extends US2 (quality ranking) but independently testable

### Within Each User Story

- **US1**: VirtualGrid foundation → AllPhotosGrid → MainWindow integration → Error handling
- **US2**: PhotoQuality service → LibraryService.get_days() → DaysView UI
- **US3**: EventClusterer service → LibraryService.get_months() → MonthsView UI
- **US4**: Quality highlights → LibraryService.get_years() → YearsView UI

### Parallel Opportunities

**Phase 1 (Setup)**:

- T002 and T003 can run in parallel (independent directory verification)

**Phase 2 (Foundational)**:

- T004 and T005 can run in parallel (different model files)
- T008 and T009 can run in parallel (different utility files)
- T010, T011, T012 must run sequentially (same file: virtual_grid.py)

**Phase 4 (US2)**:

- T032-T037 can run in parallel (different helper functions in same file with careful merge)
- Quality scoring helpers are independent

**Phase 7 (Polish)**:

- T066, T069, T070, T071, T072 can run in parallel (different files)
- T073-T075 are testing tasks (can run in parallel)
- T076 and T077 can run in parallel (different testing activities)

**Cross-Story Parallelism**:

- After Phase 2 completes, US2, US3, and US4 can be worked on in parallel by different developers
- US1 should be completed first to validate foundation

---

## Parallel Example: Foundational Phase

```bash
# These can run in parallel (different files):
Task T004: "Create LibraryItem dataclass in src/models/library_item.py"
Task T005: "Create ViewGroup entities in src/models/view_groups.py"

# After T004 and T005 complete:
Task T006: "Create LibraryService class skeleton in src/services/library_service.py"

# These can run in parallel (different utility files):
Task T008: "Create ThumbnailLoader class in src/utils/async_loader.py"
Task T009: "Modify ThumbnailCache in src/utils/thumbnail_cache.py"
```

## Parallel Example: User Story 2 Quality Scoring

```bash
# These helper functions can be developed in parallel:
Task T033: "Implement _score_iso() helper function in src/services/photo_quality.py"
Task T034: "Implement _score_camera_shake() helper function in src/services/photo_quality.py"
Task T035: "Implement _score_aperture() helper function in src/services/photo_quality.py"
Task T036: "Implement _score_exposure_comp() helper function in src/services/photo_quality.py"
Task T037: "Implement _score_flash() helper function in src/services/photo_quality.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (All Photos Grid)
4. **STOP and VALIDATE**: Test with 10,000 photos
   - Verify 60fps scrolling
   - Verify progressive thumbnail loading
   - Verify memory <500MB
5. Deploy/demo if ready - users can now view entire library

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → **DEPLOY/DEMO (MVP!)**
3. Add User Story 2 → Test independently → **DEPLOY/DEMO** (now with Days view)
4. Add User Story 3 → Test independently → **DEPLOY/DEMO** (now with Months view)
5. Add User Story 4 → Test independently → **DEPLOY/DEMO** (now with Years view)
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers (after Foundational phase completes):

1. Developer A: User Story 1 (highest priority - do this first to validate foundation)
2. After US1 validates foundation:
   - Developer A or B: User Story 2 (requires quality ranking)
   - Developer C: User Story 3 (requires event clustering - independent of US2)
   - Developer D: User Story 4 (depends on US2 quality ranking completion)
3. Stories complete and integrate independently

---

## Task Summary

- **Total Tasks**: 77
- **Setup Phase**: 3 tasks
- **Foundational Phase**: 9 tasks (BLOCKS all user stories)
- **User Story 1 (P1 - MVP)**: 19 tasks
- **User Story 2 (P2)**: 17 tasks
- **User Story 3 (P3)**: 10 tasks
- **User Story 4 (P4)**: 7 tasks
- **Integration & Polish**: 12 tasks

**Parallel Opportunities Identified**: 15+ tasks can run in parallel within phases

**Independent Test Criteria**:

- US1: View entire library in scrollable grid with 60fps performance
- US2: Browse by days with best shots highlighted
- US3: Browse by months with events clustered
- US4: Browse by years with highlights showing variety

**Suggested MVP Scope**: Phase 1 + Phase 2 + Phase 3 (User Story 1 only) = 31 tasks

---

## Performance Validation Checklist

After implementation, verify these performance targets from spec.md:

- [ ] **SC-001**: 60 fps scrolling with 10,000 photos
- [ ] **SC-002**: Thumbnails load within 2 seconds per viewport
- [ ] **SC-003**: UI remains responsive during thumbnail generation
- [ ] **SC-004**: All Photos grid displays within 1 second
- [ ] **SC-005**: View switching completes within 500ms
- [ ] **SC-006**: Thumbnail generation for 1,000 photos completes within 5 minutes
- [ ] **SC-007**: Smooth performance with 50,000 photos

---

## Notes

- All tasks follow strict checklist format: `- [ ] [TaskID] [P?] [Story?] Description with file path`
- [P] tasks = different files, no dependencies, can run in parallel
- [Story] label (US1, US2, US3, US4) maps task to specific user story for traceability
- Each user story is independently completable and testable
- Tests are NOT included (manual testing preferred per constitution)
- Constitution compliance verified: Simple architecture, performance-first design, progressive enhancement
- Research patterns validated: QListView virtual scrolling, QThreadPool async loading, EXIF quality scoring
- Memory budget validated: <500MB for 50,000 photos with LRU cache
