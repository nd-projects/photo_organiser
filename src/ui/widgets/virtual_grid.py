"""
Virtual grid widget with lazy loading for displaying large photo libraries.

This module provides a performance-optimized grid view using Qt's Model/View/Delegate
pattern with lazy loading to handle tens of thousands of photos efficiently.
"""

from PyQt6.QtWidgets import QListView, QStyledItemDelegate, QStyleOptionViewItem
from PyQt6.QtCore import (
    Qt, QAbstractListModel, QModelIndex, pyqtSignal, QSize
)
from PyQt6.QtGui import QPainter, QPixmap, QColor
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class PhotoLibraryModel(QAbstractListModel):
    """
    Qt model for library items with lazy loading support.

    This model loads items in batches as the user scrolls, enabling efficient
    display of large photo libraries (10,000+ photos).
    """

    def __init__(self, library_service, batch_size: int = 200, parent=None):
        """
        Initialize photo library model.

        Args:
            library_service: LibraryService instance for data access
            batch_size: Number of items to load per batch (default: 200)
            parent: Parent QObject
        """
        super().__init__(parent)
        self.library_service = library_service
        self.batch_size = batch_size

        # Lazy loading state
        self._items = []  # Currently loaded items
        self._total_count = 0  # Total items in library
        self._loaded_count = 0  # Number of items loaded so far

        logger.debug(f"PhotoLibraryModel initialized (batch_size={batch_size})")

    def rowCount(self, parent=QModelIndex()) -> int:
        """
        Return number of loaded rows.

        CRITICAL: Must return loaded count, not total count, for lazy loading.

        Args:
            parent: Parent index (unused for list models)

        Returns:
            Number of currently loaded items
        """
        if parent.isValid():
            return 0  # List models don't have children
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        """
        Return data for a specific item.

        Called on-demand only for visible items. Must be fast.

        Args:
            index: Model index
            role: Data role

        Returns:
            Data for the requested role, or None
        """
        if not index.isValid() or index.row() >= len(self._items):
            return None

        item = self._items[index.row()]

        if role == Qt.ItemDataRole.UserRole:
            # Return full LibraryItem for delegate
            return item

        elif role == Qt.ItemDataRole.DisplayRole:
            # Return display text (optional, for debugging)
            return item.path.name

        return None

    def canFetchMore(self, parent=QModelIndex()) -> bool:
        """
        Check if more data can be loaded.

        Args:
            parent: Parent index (unused for list models)

        Returns:
            True if more items available to load
        """
        if parent.isValid():
            return False
        return self._loaded_count < self._total_count

    def fetchMore(self, parent=QModelIndex()):
        """
        Load next batch of items.

        Called automatically by QListView when user scrolls near the end.
        Uses beginInsertRows/endInsertRows for efficient updates.

        Args:
            parent: Parent index (unused for list models)
        """
        if parent.isValid():
            return

        items_to_fetch = min(self.batch_size, self._total_count - self._loaded_count)
        if items_to_fetch <= 0:
            return

        logger.debug(f"Fetching {items_to_fetch} items (offset={self._loaded_count})")

        # Notify view that rows are being inserted
        self.beginInsertRows(
            QModelIndex(),
            self._loaded_count,
            self._loaded_count + items_to_fetch - 1
        )

        # Load batch from library service
        start = self._loaded_count
        new_items = self.library_service.get_all_items(start, items_to_fetch)
        self._items.extend(new_items)
        self._loaded_count += len(new_items)

        # Notify view that rows have been inserted
        self.endInsertRows()

        logger.debug(f"Loaded {len(new_items)} items (total loaded: {self._loaded_count}/{self._total_count})")

    def set_library(self, total_count: int):
        """
        Initialize model with total item count.

        This resets the model and triggers initial batch load.

        Args:
            total_count: Total number of items in library
        """
        logger.info(f"Setting library with {total_count} items")

        self.beginResetModel()
        self._items.clear()
        self._total_count = total_count
        self._loaded_count = 0
        self.endResetModel()

        # Trigger initial batch load
        if self.canFetchMore():
            self.fetchMore()


class ThumbnailDelegate(QStyledItemDelegate):
    """
    Custom delegate for rendering thumbnails with async loading.

    This delegate displays thumbnails with placeholder/error states and
    triggers asynchronous thumbnail loading for optimal performance.
    """

    # Signal emitted when thumbnail needs loading
    # Parameters: (source_path: Path, index: QModelIndex)
    thumbnail_requested = pyqtSignal(Path, QModelIndex)

    def __init__(self, thumbnail_cache, thumbnail_size: tuple[int, int] = (200, 200), parent=None):
        """
        Initialize thumbnail delegate.

        Args:
            thumbnail_cache: ThumbnailCache instance for checking cache
            thumbnail_size: Thumbnail size (width, height) (default: 200x200)
            parent: Parent QObject
        """
        super().__init__(parent)
        self.thumbnail_cache = thumbnail_cache
        self.thumbnail_size = thumbnail_size

        # Cache for loaded thumbnails (QPixmap can only be created in main thread)
        self.pixmap_cache: dict[int, QPixmap] = {}  # row -> QPixmap

        # Track which thumbnails have been requested (prevent duplicate requests)
        self._requested: set[int] = set()

        # Placeholder/error pixmaps (created once)
        self.placeholder = self._create_placeholder()
        self.error_pixmap = self._create_error()

        logger.debug(f"ThumbnailDelegate initialized (size={thumbnail_size})")

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        """
        Paint thumbnail for a single item.

        Called by Qt for each visible item. Performance-critical method.

        Args:
            painter: QPainter for rendering
            option: Style options
            index: Model index
        """
        if not index.isValid():
            return

        # Get LibraryItem from model
        item = index.data(Qt.ItemDataRole.UserRole)
        if not item:
            return

        row = index.row()

        # Check if we have a cached QPixmap for this row
        if row in self.pixmap_cache:
            pixmap = self.pixmap_cache[row]
        else:
            # Check if thumbnail exists on disk (fast check)
            cache_path = self.thumbnail_cache.get(item.path, self.thumbnail_size)

            if cache_path and cache_path.exists():
                # Load from cache synchronously (fast - already resized)
                pixmap = QPixmap(str(cache_path))
                if pixmap.isNull():
                    pixmap = self.error_pixmap
                else:
                    self.pixmap_cache[row] = pixmap
            else:
                # Not cached - show placeholder and request async load
                pixmap = self.placeholder

                # Emit signal for background worker to load (only once per item)
                if row not in self._requested:
                    self._requested.add(row)
                    self.thumbnail_requested.emit(item.path, index)

        # Draw the pixmap
        painter.save()

        # Draw background if selected
        from PyQt6.QtWidgets import QStyle
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        # Calculate centered position
        x = option.rect.x() + (option.rect.width() - pixmap.width()) // 2
        y = option.rect.y() + (option.rect.height() - pixmap.height()) // 2

        painter.drawPixmap(x, y, pixmap)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        """
        Return size hint for item.

        Must be consistent for all items when uniformItemSizes is True.

        Args:
            option: Style options
            index: Model index

        Returns:
            QSize for item (width, height)
        """
        # Add padding around thumbnail (200x200 thumbnail + 20px padding)
        return QSize(220, 240)

    def update_thumbnail(self, row: int, pixmap: QPixmap):
        """
        Update thumbnail pixmap for a specific row.

        Called by main thread when background worker finishes loading.

        Args:
            row: Model row to update
            pixmap: Loaded QPixmap (created from QImage in main thread)
        """
        self.pixmap_cache[row] = pixmap
        # View will repaint automatically via model.dataChanged signal

    def clear_cache(self):
        """Clear the pixmap cache to free memory."""
        self.pixmap_cache.clear()
        self._requested.clear()
        logger.debug("ThumbnailDelegate cache cleared")

    def _create_placeholder(self) -> QPixmap:
        """Create placeholder pixmap (loading state)."""
        pixmap = QPixmap(self.thumbnail_size[0], self.thumbnail_size[1])
        pixmap.fill(QColor(220, 220, 220))

        painter = QPainter(pixmap)
        painter.setPen(QColor(150, 150, 150))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Loading...")
        painter.end()

        return pixmap

    def _create_error(self) -> QPixmap:
        """Create error pixmap (failed load)."""
        pixmap = QPixmap(self.thumbnail_size[0], self.thumbnail_size[1])
        pixmap.fill(QColor(200, 100, 100))

        painter = QPainter(pixmap)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "⚠\nError")
        painter.end()

        return pixmap


class VirtualGridWidget(QListView):
    """
    Performance-optimized grid view for large photo libraries.

    Uses QListView in IconMode with uniform item sizes for maximum performance.
    Supports smooth scrolling with 10,000+ photos at 60fps.
    """

    def __init__(self, parent=None):
        """
        Initialize virtual grid widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        # Configure for grid mode
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setSpacing(10)
        self.setUniformItemSizes(True)  # CRITICAL for performance

        # Grid size (matches delegate sizeHint)
        self.setGridSize(QSize(220, 240))

        # Scrolling performance
        self.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Selection
        self.setSelectionMode(QListView.SelectionMode.ExtendedSelection)

        logger.debug("VirtualGridWidget initialized")

    def set_model_and_delegate(self, model: PhotoLibraryModel, delegate: ThumbnailDelegate):
        """
        Set model and delegate for this view.

        Args:
            model: PhotoLibraryModel instance
            delegate: ThumbnailDelegate instance
        """
        self.setModel(model)
        self.setItemDelegate(delegate)
        logger.debug("Model and delegate set")
