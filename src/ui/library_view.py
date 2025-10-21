"""
Library View - main container for photo library with multiple view modes.

This widget provides the Library tab with navigation between different view modes:
- All Photos: Complete library in chronological grid
- Days: Photos organized by day with best shots
- Months: Photos organized by month with events
- Years: Photos organized by year with highlights
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton, QLabel
)
from PyQt6.QtCore import Qt, QTime
import logging

from .all_photos_grid import AllPhotosGrid
from .days_view import DaysView

logger = logging.getLogger(__name__)


class LibraryView(QWidget):
    """
    Main Library view container with tab navigation for different view modes.

    Phase 3 (MVP): Implements "All Photos" view
    Phase 4: Adds "Days" view with best shots
    Future phases will add Months and Years views
    """

    def __init__(self, library_service, thumbnail_cache, photo_processor, parent=None):
        """
        Initialize Library view.

        Args:
            library_service: LibraryService instance for data access
            thumbnail_cache: ThumbnailCache instance for caching
            photo_processor: PhotoProcessor instance for thumbnail generation
            parent: Parent widget
        """
        super().__init__(parent)

        self.library_service = library_service
        self.thumbnail_cache = thumbnail_cache
        self.photo_processor = photo_processor

        # Track view switching time for performance monitoring (T047)
        # Initialize BEFORE connecting signal to avoid AttributeError
        self._switch_start_time = None

        # Create tab widget for view modes
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)

        # T026: Create All Photos view (Phase 3 MVP)
        self.all_photos_view = AllPhotosGrid(
            library_service,
            thumbnail_cache,
            photo_processor
        )
        self.tab_widget.addTab(self.all_photos_view, "All Photos")

        # T046: Create Days view (Phase 4 - US2)
        self.days_view = DaysView(library_service, thumbnail_cache, photo_processor)
        self.tab_widget.addTab(self.days_view, "Days")

        # Placeholder tabs for future phases
        self._add_placeholder_tab("Months", "Phase 5: User Story 3")
        self._add_placeholder_tab("Years", "Phase 6: User Story 4")

        # Connect tab change signal for performance tracking (T047)
        # Connect AFTER tabs are added to avoid initial trigger
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tab_widget)

        logger.info("LibraryView initialized (Phase 3-4: All Photos + Days)")

    def _add_placeholder_tab(self, title: str, message: str):
        """
        Add a placeholder tab for future implementation.

        Args:
            title: Tab title
            message: Message to display
        """
        placeholder = QWidget()
        layout = QVBoxLayout(placeholder)
        layout.addStretch()

        label = QLabel(f"<h2>{title}</h2><p>{message}</p>")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        layout.addStretch()

        self.tab_widget.addTab(placeholder, title)

    def load_library(self):
        """
        Load the library and initialize all views.

        Phase 3: Loads All Photos view
        Phase 4: Also loads Days view
        Future phases will add Months and Years views.
        """
        logger.info("Loading Library view...")

        # Load All Photos view (Phase 3)
        self.all_photos_view.load_library()

        # Load Days view (Phase 4 - US2)
        self.days_view.load_days()

        # Future phases will load other views here
        # self.months_view.load_months()  # Phase 5
        # self.years_view.load_years()  # Phase 6

        logger.info("Library view loaded successfully")

    def refresh(self):
        """
        Refresh the library view after data changes.

        Triggers a reload of all visible view modes.
        """
        logger.info("Refreshing Library view...")

        # Refresh current view
        current_index = self.tab_widget.currentIndex()
        if current_index == 0:  # All Photos
            self.all_photos_view.load_library()
        elif current_index == 1:  # Days (Phase 4)
            self.days_view.load_days()
        # Future: handle other tabs

        logger.info("Library view refreshed")

    def clear(self):
        """Clear all views and free resources."""
        self.all_photos_view.clear()
        logger.debug("LibraryView cleared")

    def _on_tab_changed(self, index: int):
        """
        Handle tab change event with performance monitoring.

        Implements T047: View switching performance (<500ms target)

        Args:
            index: New tab index
        """
        if self._switch_start_time is None:
            # Record start time for next switch
            self._switch_start_time = QTime.currentTime()
        else:
            # Calculate elapsed time since last switch
            elapsed_ms = self._switch_start_time.msecsTo(QTime.currentTime())

            # Log performance
            if elapsed_ms > 500:
                logger.warning(f"View switch took {elapsed_ms}ms (target: <500ms)")
            else:
                logger.info(f"View switch completed in {elapsed_ms}ms")

            # Reset for next switch
            self._switch_start_time = QTime.currentTime()

        # Log which view was switched to
        tab_name = self.tab_widget.tabText(index)
        logger.info(f"Switched to view: {tab_name}")
