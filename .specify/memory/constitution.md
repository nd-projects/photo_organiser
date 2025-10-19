<!--
Sync Impact Report
==================
Version Change: 1.0.0 → 1.1.0
Modification Type: MINOR - Added Python tooling requirement
Rationale: Added mandatory requirement that all Python operations must use uv for dependency management and command execution.

Principles Modified:
- Development Standards: Added "Python Tooling" subsection

Added Sections:
- Development Standards > Python Tooling (new subsection)

Removed Sections:
- None

Templates Status:
✅ plan-template.md - No changes needed (constitution check references principles generically)
✅ spec-template.md - No changes needed (requirements are implementation-agnostic)
✅ tasks-template.md - No changes needed (task execution handles uv via agent instructions)
✅ README.md - Already documents uv usage correctly

Follow-up TODOs:
- None - requirement aligns with existing project practice

Date: 2025-10-18
-->

# Photo Organiser Constitution

## Core Principles

### I. Code Quality & Simplicity

**Rule**: Every component MUST be simple, readable, and maintainable above all else. Complex abstractions are prohibited unless explicitly justified in the Complexity Tracking section of the implementation plan.

**Requirements**:

- Code MUST be self-documenting through clear naming and structure
- Functions MUST have a single, well-defined responsibility
- Dependencies MUST be minimized; prefer standard library solutions
- New abstractions MUST solve concrete problems, not anticipated ones (YAGNI)
- Code duplication is acceptable until patterns emerge naturally (Rule of Three)

**Rationale**: Simple code is easier to maintain, debug, and extend. Premature abstraction creates unnecessary complexity that hinders velocity and introduces bugs. Quality is measured by readability and maintainability, not cleverness.

### II. User Experience Consistency

**Rule**: All user-facing behavior, interfaces, and workflows MUST follow consistent patterns throughout the application. Inconsistency is considered a defect.

**Requirements**:

- User workflows MUST follow predictable patterns (navigation, actions, feedback)
- Visual elements MUST use consistent styling, spacing, and interaction models
- Error messages and feedback MUST be clear, actionable, and consistently formatted
- Keyboard shortcuts and accessibility features MUST work uniformly across all screens
- File naming, organization patterns, and metadata handling MUST be predictable to users

**Rationale**: Consistent UX reduces cognitive load, minimizes user errors, and creates a professional, trustworthy experience. Users should be able to predict how the application behaves based on their prior interactions.

### III. Performance First

**Rule**: Performance is a feature, not an optimization task. All implementations MUST meet performance requirements from the start.

**Requirements**:

- Operations MUST feel instantaneous (<100ms) for user interactions
- Batch operations MUST provide progress feedback and remain responsive
- Memory usage MUST be bounded and not grow with dataset size (streaming required for large data)
- File I/O MUST be asynchronous and non-blocking for user interface responsiveness
- Image loading and processing MUST use lazy loading and progressive rendering
- Startup time MUST be under 2 seconds for the application

**Rationale**: Performance directly impacts user satisfaction and perceived quality. Fixing performance issues after implementation is expensive and often requires architectural changes. Building with performance requirements from the start prevents technical debt.

### IV. Pragmatic Testing

**Rule**: Testing is pragmatic and targeted, not comprehensive. Tests are written only when they provide clear value and prevent real failures.

**Requirements**:

- Tests are OPTIONAL by default; include only when explicitly requested or when risk is high
- Integration tests are preferred over unit tests when both would provide coverage
- Manual testing and validation scripts are acceptable for UI and workflow verification
- Critical algorithms (file integrity, metadata parsing, duplicate detection) SHOULD have focused tests
- Testing MUST NOT block feature development unless failures represent data loss risk

**Exceptions requiring tests**:

- Data migration or transformation logic (risk: data corruption)
- File system operations that could cause data loss
- Complex business logic with multiple edge cases

**Rationale**: Testing overhead can slow development without proportional benefit. Real-world usage and progressive deployment are often more effective at finding issues. We prioritize shipping working features and iterating based on user feedback over achieving test coverage targets.

### V. Progressive Enhancement

**Rule**: Features MUST be built in incremental, independently valuable slices. Each slice MUST be fully functional and deployable on its own.

**Requirements**:

- User stories MUST be prioritized (P1, P2, P3...) and independently implementable
- P1 user story MUST represent a viable MVP that delivers core value
- Each completed user story MUST be demonstrable and usable without subsequent stories
- New features MUST NOT break existing functionality
- Feature flags or incremental rollout strategies MUST be used for risky changes

**Rationale**: Progressive enhancement enables faster feedback cycles, reduces risk, and allows course correction based on real user needs. Shipping a minimal but complete feature is better than shipping an incomplete comprehensive feature.

## Performance Standards

All implementations MUST meet these measurable performance criteria:

### Response Time Targets

- **User interactions**: <100ms for UI responsiveness (button clicks, navigation)
- **Image thumbnail generation**: <500ms per image
- **Metadata extraction**: <200ms per file
- **Search operations**: <300ms for queries across 10,000+ photos
- **Duplicate detection**: Streaming results (first results <2 seconds, full scan background)

### Resource Constraints

- **Memory**: Bounded growth; MUST NOT exceed 500MB for UI + processing
- **Disk I/O**: Streaming for operations over 100 files
- **CPU**: Background processing MUST NOT block UI (use worker threads/processes)
- **Startup**: Application ready in <2 seconds

### Scalability Requirements

- Application MUST handle collections of 50,000+ photos without degradation
- Filtering and sorting MUST use indexed/efficient algorithms (O(n log n) or better)
- Large batch operations MUST be cancellable and resumable

**Justification**: Photo organization involves large files and datasets. Poor performance makes the application unusable and frustrating. These standards ensure the application remains responsive and professional at scale.

## Development Standards

### Python Tooling

**Rule**: All Python operations MUST be executed using `uv` as the package manager and command runner.

**Requirements**:

- Dependency installation MUST use `uv sync` (not `pip install`)
- Script execution MUST use `uv run <command>` (not direct python invocation)
- Virtual environment management MUST be handled by `uv` (not virtualenv/venv)
- New dependencies MUST be added via `uv add <package>` (not manual pyproject.toml edits)
- Development dependencies MUST use `uv add --dev <package>`
- All test commands MUST use `uv run pytest` (not direct pytest invocation)

**Prohibited**:

- Direct use of `pip`, `pip install`, `pip freeze`
- Direct use of `python -m`, `python script.py` (use `uv run python` instead)
- Manual creation of virtual environments with `venv` or `virtualenv`

**Rationale**: `uv` provides faster dependency resolution, deterministic builds, and better compatibility handling than traditional pip-based workflows. Standardizing on uv ensures consistent environments across development and prevents dependency conflicts. The project is already built with uv, and all tooling must respect this architectural decision.

### Code Organization

- Follow standard project structure conventions for the chosen language/framework
- Group related functionality (features) together, not by technical layer
- Minimize cross-feature dependencies; prefer composition over inheritance
- Configuration MUST be externalized (environment variables, config files)

### Error Handling

- All file system operations MUST handle errors gracefully (permissions, missing files, corruption)
- Error messages MUST be user-friendly and actionable
- Crashes and data loss are NEVER acceptable; defensive programming is required
- Log errors with sufficient context for debugging (file paths, operation, error details)

### Documentation

- Public APIs and complex algorithms MUST have clear documentation
- User-facing features MUST have usage documentation or in-app guidance
- README MUST explain setup, usage, and architecture at a high level
- Inline comments are for "why" not "what"; prefer self-documenting code

### Version Control

- Commits MUST be atomic (single logical change) and have clear messages
- Commit messages MUST NOT include co-authoring attribution (per user's global instructions)
- Feature work MUST happen in feature branches
- Main branch MUST always be in a deployable state

## Governance

### Amendment Process

1. Proposed changes MUST be documented with rationale and impact analysis
2. Constitution version MUST be incremented following semantic versioning:
   - **MAJOR**: Backward-incompatible principle changes or removals
   - **MINOR**: New principles or sections added
   - **PATCH**: Clarifications, wording improvements, typo fixes
3. All dependent templates (plan, spec, tasks, checklist) MUST be reviewed and updated for consistency

### Compliance

- All feature implementations MUST pass the Constitution Check in the implementation plan
- Code reviews MUST verify adherence to principles
- Violations MUST be justified in the Complexity Tracking section of the plan
- Unjustified violations MUST be refactored before merge

### Versioning and Tracking

- This constitution supersedes all other development practices
- Changes to principles require updating LAST_AMENDED_DATE
- Major architectural decisions MUST reference relevant constitutional principles

**Version**: 1.1.0 | **Ratified**: 2025-10-15 | **Last Amended**: 2025-10-18
