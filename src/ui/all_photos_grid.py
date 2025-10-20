"""
All Photos Grid view - displays entire library in a scrollable grid.

This view provides the "All Photos" view mode showing all media items
in chronological order with efficient lazy loading and async thumbnails.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import pyqtSlot, QModelIndex
from PyQt6.QtGui import QPixmap, QImage
from pathlib import Path
import logging

from .widgets.virtual_grid import VirtualGridWidget, PhotoLibraryModel, ThumbnailDelegate
from ..utils.async_loader import ThumbnailLoader
from ..services.photo_processor import PhotoProcessor

logger = logging.getLogger(__name__)


class AllPhotosGrid(QWidget):
    """
    All Photos view widget - displays all library items in a virtual scrolling grid.

    This widget integrates:
    - VirtualGridWidget for efficient grid display
    - PhotoLibraryModel for lazy loading
    - ThumbnailDelegate for async thumbnail rendering
    - ThumbnailLoader for background thumbnail generation
    """

    def __init__(self, library_service, thumbnail_cache, photo_processor, parent=None):
        """
        Initialize All Photos grid.

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

        # Create model
        self.model = PhotoLibraryModel(library_service, batch_size=200)

        # Create delegate
        thumbnail_size = (200, 200)
        self.delegate = ThumbnailDelegate(thumbnail_cache, thumbnail_size)

        # Create grid view
        self.grid = VirtualGridWidget()
        self.grid.set_model_and_delegate(self.model, self.delegate)

        # Create thumbnail loader
        self.loader = ThumbnailLoader(photo_processor, thumbnail_cache)

        # Connect signals (T023 & T024)
        self._connect_signals()

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.grid)

        logger.info("AllPhotosGrid initialized")

    def _connect_signals(self):
        """
        Connect signals between delegate and loader.

        Implements T023 and T024:
        - T023: Connect thumbnail_requested signal to loader
        - T024: Connect thumbnail_ready signal to update delegate
        """
        # T023: Connect delegate's thumbnail request to loader
        self.delegate.thumbnail_requested.connect(self._on_thumbnail_requested)

        logger.debug("AllPhotosGrid signals connected")

    @pyqtSlot(Path, QModelIndex)
    def _on_thumbnail_requested(self, source_path: Path, index: QModelIndex):
        """
        Handle thumbnail request from delegate.

        This method queues the thumbnail for background generation and
        connects the worker's signals to handle completion.

        Args:
            source_path: Path to source image
            index: Model index
        """
        row = index.row()
        size = self.delegate.thumbnail_size

        # Queue thumbnail for loading (priority 0 = high/visible)
        worker = self.loader.queue_thumbnail(row, source_path, size, priority=0)

        # T024: Connect worker signals to update delegate when ready
        worker.signals.thumbnail_ready.connect(self._on_thumbnail_ready)
        worker.signals.thumbnail_failed.connect(self._on_thumbnail_failed)

    @pyqtSlot(int, Path)
    def _on_thumbnail_ready(self, row: int, thumbnail_path: Path):
        """
        Handle successful thumbnail generation.

        Loads the thumbnail from disk and updates the delegate cache,
        then triggers a repaint of the item.

        Args:
            row: Model row index
            thumbnail_path: Path to generated thumbnail
        """
        try:
            # Load QImage from disk (thread-safe)
            image = QImage(str(thumbnail_path))

            if not image.isNull():
                # Convert to QPixmap (must be done in main thread)
                pixmap = QPixmap.fromImage(image)

                # Update delegate cache
                self.delegate.update_thumbnail(row, pixmap)

                # Trigger repaint of this item
                index = self.model.index(row, 0)
                self.model.dataChanged.emit(index, index)

                logger.debug(f"Thumbnail loaded for row {row}")
            else:
                logger.warning(f"Failed to load image from {thumbnail_path}")
                self._on_thumbnail_failed(row, "Image load returned null")

        except Exception as e:
            logger.error(f"Error loading thumbnail for row {row}: {e}")
            self._on_thumbnail_failed(row, str(e))

    @pyqtSlot(int, str)
    def _on_thumbnail_failed(self, row: int, error_message: str):
        """
        Handle thumbnail generation failure.

        Updates the delegate to show error pixmap for this item.

        Args:
            row: Model row index
            error_message: Error description
        """
        logger.warning(f"Thumbnail failed for row {row}: {error_message}")

        # Update delegate with error pixmap
        self.delegate.update_thumbnail(row, self.delegate.error_pixmap)

        # Trigger repaint of this item
        index = self.model.index(row, 0)
        self.model.dataChanged.emit(index, index)

    def load_library(self):
        """
        Load the library and display all photos.

        This initializes the model with the total count and triggers
        the initial batch load.
        """
        total_count = self.library_service.get_total_count()
        logger.info(f"Loading All Photos view with {total_count} items")

        # Clear delegate cache (in case this is a reload)
        self.delegate.clear_cache()

        # Set model total count (triggers initial fetch)
        self.model.set_library(total_count)

        logger.info(f"All Photos view loaded successfully")

    def clear(self):
        """Clear the grid and free resources."""
        self.delegate.clear_cache()
        self.model.set_library(0)
        logger.debug("AllPhotosGrid cleared")
