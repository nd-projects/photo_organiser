"""
Days View Widget

Displays photos organized chronologically by day with best shots highlighted.
Part of Phase 4 (User Story 2) implementation.

Date: 2025-10-20
Feature: Library View (002-library-view)
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QLabel, QFrame, QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, pyqtSlot
from PyQt6.QtGui import QFont, QPixmap, QImage
from pathlib import Path
from typing import Optional
import logging

from ..models.view_groups import DayGroup
from ..services.library_service import LibraryService
from ..utils.async_loader import ThumbnailLoader
from .widgets.thumbnail_widget import ThumbnailWidget

logger = logging.getLogger(__name__)


class DaysView(QWidget):
    """
    Widget for displaying photos organized by days with best shots highlighted.

    Features:
    - Scrollable day sections (reverse chronological)
    - Best shots (top 5) highlighted per day
    - Day headers with date and photo count
    - Skips days without photos
    """

    # Signal emitted when photo is clicked
    photo_clicked = pyqtSignal(Path)

    def __init__(self, library_service: LibraryService, thumbnail_cache, photo_processor, parent=None):
        """
        Initialize DaysView.

        Args:
            library_service: Service for accessing library data
            thumbnail_cache: ThumbnailCache instance for caching
            photo_processor: PhotoProcessor instance for thumbnail generation
            parent: Parent widget
        """
        super().__init__(parent)

        self.library_service = library_service
        self.thumbnail_cache = thumbnail_cache
        self.photo_processor = photo_processor

        # Create thumbnail loader
        self.loader = ThumbnailLoader(photo_processor, thumbnail_cache)

        # Track thumbnail requests for cleanup
        self._thumbnail_widgets = {}  # {row: ThumbnailWidget}
        self._thumbnail_row_counter = 0

        # Setup UI
        self._setup_ui()

        logger.info("DaysView initialized")

    def _setup_ui(self):
        """Setup the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Scroll area for day sections
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Container for day sections
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setSpacing(20)
        self.container_layout.setContentsMargins(20, 20, 20, 20)

        self.scroll_area.setWidget(self.container)
        main_layout.addWidget(self.scroll_area)

    def load_days(self, year: Optional[int] = None, month: Optional[int] = None):
        """
        Load and display days from library service.

        Args:
            year: Filter by year (None = all years)
            month: Filter by month (None = all months)
        """
        logger.info(f"Loading days (year={year}, month={month})")

        # Clear existing content
        self._clear_container()

        # Get day groups from service
        try:
            day_groups = self.library_service.get_days(year=year, month=month)

            if not day_groups:
                self._show_empty_message()
                return

            # Create section for each day (skip days without photos)
            for day_group in day_groups:
                if day_group.total_count > 0:  # Only show days with content
                    day_section = self._create_day_section(day_group)
                    self.container_layout.addWidget(day_section)

            # Add stretch at end
            self.container_layout.addStretch()

            logger.info(f"Loaded {len(day_groups)} days")

        except Exception as e:
            logger.error(f"Failed to load days: {e}")
            self._show_error_message(str(e))

    def _create_day_section(self, day_group: DayGroup) -> QWidget:
        """
        Create a section widget for a single day.

        Args:
            day_group: Day group data

        Returns:
            Widget containing day header and photos
        """
        # Container frame
        section = QFrame()
        section.setFrameShape(QFrame.Shape.StyledPanel)
        section.setFrameShadow(QFrame.Shadow.Raised)

        layout = QVBoxLayout(section)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # Day header
        header = self._create_day_header(day_group)
        layout.addWidget(header)

        # Best shots section (if any)
        if day_group.best_shots:
            best_shots_widget = self._create_best_shots_grid(day_group.best_shots)
            layout.addWidget(best_shots_widget)

            # Separator between best shots and all photos
            separator = QFrame()
            separator.setFrameShape(QFrame.Shape.HLine)
            separator.setFrameShadow(QFrame.Shadow.Sunken)
            layout.addWidget(separator)

        # All photos for the day
        all_photos_widget = self._create_photos_grid(day_group.items)
        layout.addWidget(all_photos_widget)

        return section

    def _create_day_header(self, day_group: DayGroup) -> QWidget:
        """
        Create header widget for day section.

        Args:
            day_group: Day group data

        Returns:
            Header widget with date and count
        """
        header = QWidget()
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Date label
        date_label = QLabel(day_group.display_title)
        date_font = QFont()
        date_font.setPointSize(16)
        date_font.setBold(True)
        date_label.setFont(date_font)
        layout.addWidget(date_label)

        # Count label
        count_text = f"{day_group.photo_count} photo{'s' if day_group.photo_count != 1 else ''}"
        if day_group.video_count > 0:
            count_text += f", {day_group.video_count} video{'s' if day_group.video_count != 1 else ''}"

        count_label = QLabel(count_text)
        count_font = QFont()
        count_font.setPointSize(10)
        count_label.setFont(count_font)
        count_label.setStyleSheet("color: #666666;")
        layout.addWidget(count_label)

        return header

    def _create_best_shots_grid(self, best_shots: list) -> QWidget:
        """
        Create grid widget for best shots with highlighting.

        Args:
            best_shots: List of LibraryItem objects (top 5)

        Returns:
            Widget containing best shots grid
        """
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # "Best Shots" label
        label = QLabel("✨ Best Shots")
        label_font = QFont()
        label_font.setPointSize(12)
        label_font.setBold(True)
        label.setFont(label_font)
        label.setStyleSheet("color: #FFD700;")  # Gold color
        layout.addWidget(label)

        # Grid for best shots
        grid = self._create_photos_grid(best_shots, highlight=True)
        layout.addWidget(grid)

        return container

    def _create_photos_grid(self, items: list, highlight: bool = False) -> QWidget:
        """
        Create grid widget for displaying photos.

        Args:
            items: List of LibraryItem objects
            highlight: If True, apply highlighting style

        Returns:
            Widget containing photo grid
        """
        container = QWidget()
        grid_layout = QGridLayout(container)
        grid_layout.setSpacing(10)
        grid_layout.setContentsMargins(0, 0, 0, 0)

        # Calculate grid dimensions (5 columns)
        columns = 5
        thumbnail_size = 180 if highlight else 150

        # Add thumbnails to grid
        for idx, item in enumerate(items):
            row = idx // columns
            col = idx % columns

            # Create thumbnail placeholder (will be replaced with actual thumbnail widget)
            thumbnail = self._create_thumbnail_widget(item, thumbnail_size, highlight)
            grid_layout.addWidget(thumbnail, row, col)

        return container

    def _create_thumbnail_widget(self, item, size: int, highlight: bool) -> QWidget:
        """
        Create thumbnail widget for a photo with async loading.

        Args:
            item: LibraryItem object
            size: Thumbnail size in pixels
            highlight: If True, apply highlighting border

        Returns:
            ThumbnailWidget with async thumbnail loading
        """
        # Create ThumbnailWidget
        thumbnail = ThumbnailWidget(item.path, (size, size))

        # Apply highlighting border if this is a best shot
        if highlight:
            thumbnail.setStyleSheet("""
                ThumbnailWidget {
                    border: 3px solid #FFD700;
                    background-color: #FFFEF0;
                }
            """)

        # Connect click signal
        thumbnail.photo_clicked.connect(lambda path: self.photo_clicked.emit(path))

        # Assign unique row ID for tracking
        row = self._thumbnail_row_counter
        self._thumbnail_row_counter += 1
        self._thumbnail_widgets[row] = thumbnail

        # Check if thumbnail exists in cache
        cache_path = self.thumbnail_cache.get(item.path, (size, size))

        if cache_path and cache_path.exists():
            # Load from cache immediately
            self._load_cached_thumbnail(thumbnail, cache_path)
        else:
            # Queue for async generation
            self._queue_thumbnail(row, item.path, (size, size), thumbnail)

        return thumbnail

    def _load_cached_thumbnail(self, tile: ThumbnailWidget, cache_path: Path):
        """
        Load thumbnail from cache synchronously.

        Args:
            tile: ThumbnailWidget to update
            cache_path: Path to cached thumbnail
        """
        try:
            pixmap = QPixmap(str(cache_path))
            if not pixmap.isNull():
                tile.set_thumbnail(pixmap)
            else:
                logger.warning(f"Failed to load cached thumbnail: {cache_path}")
        except Exception as e:
            logger.error(f"Error loading cached thumbnail: {e}")

    def _queue_thumbnail(self, row: int, source_path: Path, size: tuple, tile: ThumbnailWidget):
        """
        Queue thumbnail for async generation.

        Args:
            row: Unique row ID for tracking
            source_path: Path to source image
            size: Thumbnail size (width, height)
            tile: ThumbnailWidget to update
        """
        # Queue thumbnail for loading (priority 0 = high/visible)
        worker = self.loader.queue_thumbnail(row, source_path, size, priority=0)

        # Connect worker signals
        worker.signals.thumbnail_ready.connect(
            lambda r, path: self._on_thumbnail_ready(r, path) if r == row else None
        )
        worker.signals.thumbnail_failed.connect(
            lambda r, err: self._on_thumbnail_failed(r, err) if r == row else None
        )

    @pyqtSlot(int, Path)
    def _on_thumbnail_ready(self, row: int, thumbnail_path: Path):
        """
        Handle successful thumbnail generation.

        Args:
            row: Row ID
            thumbnail_path: Path to generated thumbnail
        """
        if row not in self._thumbnail_widgets:
            return

        tile = self._thumbnail_widgets[row]

        try:
            # Load QImage from disk (thread-safe)
            image = QImage(str(thumbnail_path))

            if not image.isNull():
                # Convert to QPixmap (must be done in main thread)
                pixmap = QPixmap.fromImage(image)

                # Update tile
                tile.set_thumbnail(pixmap)

                logger.debug(f"Thumbnail loaded for row {row}")
            else:
                logger.warning(f"Failed to load image from {thumbnail_path}")
                tile.show_error()

        except Exception as e:
            logger.error(f"Error loading thumbnail for row {row}: {e}")
            tile.show_error()

    @pyqtSlot(int, str)
    def _on_thumbnail_failed(self, row: int, error_message: str):
        """
        Handle thumbnail generation failure.

        Args:
            row: Row ID
            error_message: Error description
        """
        if row not in self._thumbnail_widgets:
            return

        tile = self._thumbnail_widgets[row]
        tile.show_error()
        logger.warning(f"Thumbnail failed for row {row}: {error_message}")

    def _clear_container(self):
        """Clear all widgets from container and reset thumbnail tracking."""
        while self.container_layout.count():
            child = self.container_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Clear thumbnail tracking
        self._thumbnail_widgets.clear()
        self._thumbnail_row_counter = 0

    def _show_empty_message(self):
        """Show message when no photos found."""
        label = QLabel("No photos found for the selected period.")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_font = QFont()
        label_font.setPointSize(14)
        label.setFont(label_font)
        label.setStyleSheet("color: #999999;")
        self.container_layout.addWidget(label)
        self.container_layout.addStretch()

    def _show_error_message(self, error: str):
        """Show error message."""
        label = QLabel(f"Error loading days: {error}")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_font = QFont()
        label_font.setPointSize(12)
        label.setFont(label_font)
        label.setStyleSheet("color: #FF0000;")
        self.container_layout.addWidget(label)
        self.container_layout.addStretch()
