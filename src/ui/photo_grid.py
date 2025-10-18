"""Photo grid view for displaying photos within an album.

Uses PyQt6's QListWidget in Icon mode for efficient rendering of photo collections.
Supports RAW-JPEG deduplication, selection, and lightbox viewing.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel,
    QRubberBand, QApplication, QMenu, QDialog, QDialogButtonBox,
    QListView, QMessageBox
)
from PyQt6.QtCore import Qt, QSize, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction
from typing import Optional, Callable, List
from pathlib import Path

from ..models.photo import Photo, PhotoPair
from ..models.album import Album


class PhotoGrid(QWidget):
    """Grid view for displaying photos within an album.

    Features:
    - QListWidget in Icon mode for efficient grid rendering
    - Click to open photo in lightbox
    - Multi-select with Ctrl+Click and drag-to-select
    - RAW-JPEG deduplication display
    - Empty state message when no photos
    - Responsive grid layout with automatic wrapping
    """

    # Signals
    photo_clicked = pyqtSignal(object, int)  # (Photo/PhotoPair, index)
    photo_double_clicked = pyqtSignal(object, int)  # (Photo/PhotoPair, index)
    selection_changed = pyqtSignal(list)  # List of selected indices
    move_photos_requested = pyqtSignal(list, object)  # (photo_paths, destination_album)

    def __init__(
        self,
        parent=None,
        on_photo_click: Optional[Callable] = None,
        on_photo_double_click: Optional[Callable] = None
    ):
        """Initialize photo grid view.

        Args:
            parent: Parent widget
            on_photo_click: Callback when photo is clicked (photo, index) -> None
            on_photo_double_click: Callback when photo is double-clicked
        """
        super().__init__(parent)

        self.on_photo_click = on_photo_click
        self.on_photo_double_click = on_photo_double_click

        # State
        self._photos: List = []  # List[Photo | PhotoPair]
        self._album: Optional[Album] = None
        self._showing_empty_state = False
        self._selected_indices: List[int] = []
        self._available_albums: List[Album] = []  # For move dialog

        # Rubber band for drag selection
        self._rubber_band: Optional[QRubberBand] = None
        self._rubber_band_origin: Optional[QPoint] = None

        # Create UI
        self._create_widgets()

        # Connect signals
        if self.on_photo_click:
            self.photo_clicked.connect(self.on_photo_click)
        if self.on_photo_double_click:
            self.photo_double_clicked.connect(self.on_photo_double_click)

    def _create_widgets(self):
        """Create child widgets."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # QListWidget in Icon mode for grid display
        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_widget.setIconSize(QSize(140, 140))
        self.list_widget.setSpacing(10)
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setMovement(QListWidget.Movement.Static)
        self.list_widget.setUniformItemSizes(True)  # Performance optimization
        self.list_widget.setWordWrap(False)

        # Enable multi-selection
        self.list_widget.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection
        )

        # Enable grid flow
        self.list_widget.setFlow(QListWidget.Flow.LeftToRight)
        self.list_widget.setWrapping(True)

        # Enable context menu
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)

        # Connect item interactions
        self.list_widget.itemClicked.connect(self._handle_item_click)
        self.list_widget.itemDoubleClicked.connect(self._handle_item_double_click)
        self.list_widget.itemSelectionChanged.connect(self._handle_selection_change)

        layout.addWidget(self.list_widget)

        # Empty state label (hidden by default)
        self.empty_label = QLabel(
            "No photos in this album\n\nAdd photos to this album directory to see them here."
        )
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: gray; font-size: 14px;")
        self.empty_label.setWordWrap(True)
        self.empty_label.hide()
        layout.addWidget(self.empty_label)

    def _handle_item_click(self, item: QListWidgetItem):
        """Handle list widget item click.

        Args:
            item: Clicked list widget item
        """
        # Get photo/pair and index from item data
        photo_or_pair = item.data(Qt.ItemDataRole.UserRole)
        index = self.list_widget.row(item)

        if photo_or_pair is not None:
            self.photo_clicked.emit(photo_or_pair, index)

    def _handle_item_double_click(self, item: QListWidgetItem):
        """Handle list widget item double-click.

        Args:
            item: Double-clicked list widget item
        """
        # Get photo/pair and index from item data
        photo_or_pair = item.data(Qt.ItemDataRole.UserRole)
        index = self.list_widget.row(item)

        if photo_or_pair is not None:
            self.photo_double_clicked.emit(photo_or_pair, index)

    def _handle_selection_change(self):
        """Handle selection change in list widget."""
        selected_items = self.list_widget.selectedItems()
        selected_indices = [self.list_widget.row(item) for item in selected_items]

        self._selected_indices = selected_indices
        self.selection_changed.emit(selected_indices)

    def set_album(self, album: Album):
        """Set the album whose photos to display.

        Args:
            album: Album object
        """
        self._album = album

    def set_photos(self, photos: List):
        """Set photos to display in the grid.

        Args:
            photos: List of Photo or PhotoPair objects
        """
        self._photos = photos

        if len(photos) == 0:
            self._show_empty_state()
        else:
            self._hide_empty_state()
            self._populate_list(photos)

    def _populate_list(self, photos: List):
        """Populate the list widget with photo items.

        Args:
            photos: List of Photo or PhotoPair objects
        """
        self.list_widget.clear()

        for idx, photo_or_pair in enumerate(photos):
            item = QListWidgetItem()

            # Store photo/pair in item data
            item.setData(Qt.ItemDataRole.UserRole, photo_or_pair)

            # Get display path
            display_path = self._get_display_path(photo_or_pair)

            # Set thumbnail (placeholder for now, actual thumbnails loaded later)
            thumbnail_path = self._get_thumbnail_path(photo_or_pair)
            if thumbnail_path and thumbnail_path.exists():
                pixmap = QPixmap(str(thumbnail_path))
                if not pixmap.isNull():
                    # Scale to fit icon size
                    scaled = pixmap.scaled(
                        140, 140,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )

                    # Add RAW badge if this is a pair
                    if isinstance(photo_or_pair, PhotoPair) and photo_or_pair.has_raw:
                        scaled = self._add_raw_badge(scaled)

                    item.setIcon(QIcon(scaled))
                else:
                    item.setIcon(QIcon(self._create_error_pixmap()))
            else:
                # Placeholder
                item.setIcon(QIcon(self._create_placeholder_pixmap()))

            # Set filename as text (optional, can be hidden)
            if display_path:
                item.setText(display_path.name)

            # Set size hint
            item.setSizeHint(QSize(150, 170))

            self.list_widget.addItem(item)

    def _get_display_path(self, photo_or_pair) -> Optional[Path]:
        """Get display path from Photo or PhotoPair.

        Args:
            photo_or_pair: Photo or PhotoPair object

        Returns:
            Path to display
        """
        if isinstance(photo_or_pair, PhotoPair):
            return photo_or_pair.display_path
        elif isinstance(photo_or_pair, Photo):
            return photo_or_pair.path
        return None

    def _get_thumbnail_path(self, photo_or_pair) -> Optional[Path]:
        """Get thumbnail path from Photo or PhotoPair.

        Args:
            photo_or_pair: Photo or PhotoPair object

        Returns:
            Path to thumbnail or None
        """
        # Import here to avoid circular dependency
        from pathlib import Path as PathLib
        cache_dir = PathLib.cwd() / "data" / "thumbnails"

        if isinstance(photo_or_pair, PhotoPair):
            # Use JPEG thumbnail for pairs - compute cache path
            from ..utils.thumbnail_cache import ThumbnailCache
            cache = ThumbnailCache(cache_dir)
            return cache.get(photo_or_pair.display_path, (150, 150))
        elif isinstance(photo_or_pair, Photo):
            # For Photo objects, check if thumbnail_path is set, otherwise compute it
            if photo_or_pair.thumbnail_path:
                return photo_or_pair.thumbnail_path
            from ..utils.thumbnail_cache import ThumbnailCache
            cache = ThumbnailCache(cache_dir)
            return cache.get(photo_or_pair.path, (150, 150))
        return None

    def _create_placeholder_pixmap(self) -> QPixmap:
        """Create placeholder pixmap for loading state.

        Returns:
            Placeholder pixmap
        """
        pixmap = QPixmap(140, 140)
        pixmap.fill(QColor(220, 220, 220))

        painter = QPainter(pixmap)
        painter.setPen(QColor(150, 150, 150))
        from PyQt6.QtGui import QFont
        painter.setFont(QFont("Arial", 10))
        painter.drawText(
            pixmap.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "Loading..."
        )
        painter.end()

        return pixmap

    def _create_error_pixmap(self) -> QPixmap:
        """Create error pixmap for failed loads.

        Returns:
            Error pixmap
        """
        pixmap = QPixmap(140, 140)
        pixmap.fill(QColor(200, 100, 100))

        painter = QPainter(pixmap)
        painter.setPen(QColor(255, 255, 255))
        from PyQt6.QtGui import QFont
        painter.setFont(QFont("Arial", 10))
        painter.drawText(
            pixmap.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "⚠\nError"
        )
        painter.end()

        return pixmap

    def _add_raw_badge(self, pixmap: QPixmap) -> QPixmap:
        """Add RAW badge overlay to pixmap.

        Args:
            pixmap: Original pixmap

        Returns:
            Pixmap with badge
        """
        # Create a copy with badge
        result = QPixmap(pixmap.size())
        result.fill(Qt.GlobalColor.transparent)

        painter = QPainter(result)
        painter.drawPixmap(0, 0, pixmap)

        # Draw badge in top-right corner
        badge_width = 40
        badge_height = 18
        margin = 4

        badge_rect = QRect(
            pixmap.width() - badge_width - margin,
            margin,
            badge_width,
            badge_height
        )

        painter.fillRect(badge_rect, QColor(255, 140, 0, 200))  # Orange

        painter.setPen(Qt.GlobalColor.white)
        from PyQt6.QtGui import QFont
        painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        painter.drawText(
            badge_rect,
            Qt.AlignmentFlag.AlignCenter,
            "RAW"
        )

        painter.end()

        return result

    def get_photos(self) -> List:
        """Get currently displayed photos.

        Returns:
            List of Photo or PhotoPair objects
        """
        return self._photos.copy()

    def get_selected_photos(self) -> List:
        """Get currently selected photos.

        Returns:
            List of selected Photo or PhotoPair objects
        """
        return [self._photos[i] for i in self._selected_indices if i < len(self._photos)]

    def get_selected_indices(self) -> List[int]:
        """Get indices of selected photos.

        Returns:
            List of selected indices
        """
        return self._selected_indices.copy()

    def clear_selection(self):
        """Clear photo selection."""
        self.list_widget.clearSelection()
        self._selected_indices.clear()

    def select_photo(self, index: int):
        """Select photo at index.

        Args:
            index: Index of photo to select
        """
        if 0 <= index < self.list_widget.count():
            item = self.list_widget.item(index)
            item.setSelected(True)

    def select_all(self):
        """Select all photos."""
        self.list_widget.selectAll()

    def clear(self):
        """Clear all photos from the grid."""
        self._photos.clear()
        self.list_widget.clear()
        self._show_empty_state()

    def refresh(self):
        """Refresh the grid display."""
        if len(self._photos) > 0:
            self._populate_list(self._photos)

    def update_photo_thumbnail(self, index: int, thumbnail_path: Path):
        """Update thumbnail for a specific photo.

        Args:
            index: Index of photo to update
            thumbnail_path: Path to new thumbnail
        """
        if 0 <= index < self.list_widget.count():
            item = self.list_widget.item(index)
            if item:
                pixmap = QPixmap(str(thumbnail_path))
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        140, 140,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )

                    # Add RAW badge if needed
                    photo_or_pair = item.data(Qt.ItemDataRole.UserRole)
                    if isinstance(photo_or_pair, PhotoPair) and photo_or_pair.has_raw:
                        scaled = self._add_raw_badge(scaled)

                    item.setIcon(QIcon(scaled))

    def scroll_to_top(self):
        """Scroll to the top of the grid."""
        self.list_widget.scrollToTop()

    def scroll_to_photo(self, index: int):
        """Scroll to show a specific photo.

        Args:
            index: Index of photo to scroll to
        """
        if 0 <= index < self.list_widget.count():
            item = self.list_widget.item(index)
            if item:
                self.list_widget.scrollToItem(item)

    def _show_empty_state(self):
        """Show empty state message."""
        if not self._showing_empty_state:
            self.list_widget.hide()
            self.empty_label.show()
            self._showing_empty_state = True

    def _hide_empty_state(self):
        """Hide empty state message."""
        if self._showing_empty_state:
            self.empty_label.hide()
            self.list_widget.show()
            self._showing_empty_state = False

    def update_empty_message(self, message: str):
        """Update the empty state message.

        Args:
            message: New empty state message
        """
        self.empty_label.setText(message)

    def get_photo_count(self) -> int:
        """Get count of photos in the grid.

        Returns:
            Number of photos
        """
        return len(self._photos)

    def get_album(self) -> Optional[Album]:
        """Get the current album.

        Returns:
            Album object or None
        """
        return self._album

    def set_available_albums(self, albums: List[Album]):
        """Set the list of available albums for move operations.

        Args:
            albums: List of Album objects
        """
        self._available_albums = albums

    def _show_context_menu(self, position: QPoint):
        """Show context menu for selected photos.

        Args:
            position: Position where menu was requested
        """
        # Only show menu if there are selected photos
        if not self._selected_indices:
            return

        menu = QMenu(self)

        # Move to album action
        move_action = QAction("Move to Album...", self)
        move_action.triggered.connect(self._handle_move_to_album)
        menu.addAction(move_action)

        # Show menu at cursor position
        menu.exec(self.list_widget.mapToGlobal(position))

    def _handle_move_to_album(self):
        """Handle move to album action from context menu."""
        # Get selected photos
        selected_photos = self.get_selected_photos()
        if not selected_photos:
            return

        # Show album selection dialog
        destination_album = self._show_album_selection_dialog()
        if destination_album is None:
            return  # User cancelled

        # Get file paths from photos/pairs
        photo_paths = []
        for photo_or_pair in selected_photos:
            if isinstance(photo_or_pair, PhotoPair):
                # Add JPEG path (manager will detect and move RAW too)
                photo_paths.append(photo_or_pair.display_path)
            elif isinstance(photo_or_pair, Photo):
                photo_paths.append(photo_or_pair.path)

        # Emit signal to request move
        self.move_photos_requested.emit(photo_paths, destination_album)

    def _show_album_selection_dialog(self) -> Optional[Album]:
        """Show dialog to select destination album.

        Returns:
            Selected Album or None if cancelled
        """
        # Filter out current album from available albums
        available = [
            album for album in self._available_albums
            if album.path != self._album.path
        ] if self._album else self._available_albums

        if not available:
            QMessageBox.warning(
                self,
                "No Albums Available",
                "There are no other albums to move photos to.\n\n"
                "Create another album first."
            )
            return None

        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Destination Album")
        dialog.setModal(True)
        dialog.resize(400, 300)

        layout = QVBoxLayout(dialog)

        # Instructions
        label = QLabel(f"Select album to move {len(self._selected_indices)} photo(s) to:")
        layout.addWidget(label)

        # Album list
        album_list = QListWidget()
        album_list.setViewMode(QListWidget.ViewMode.ListMode)

        for album in available:
            item = QListWidgetItem(album.display_name)
            item.setData(Qt.ItemDataRole.UserRole, album)
            album_list.addItem(item)

        layout.addWidget(album_list)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        # Handle double-click to select
        album_list.itemDoubleClicked.connect(dialog.accept)

        # Show dialog
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_items = album_list.selectedItems()
            if selected_items:
                return selected_items[0].data(Qt.ItemDataRole.UserRole)

        return None

    def __str__(self) -> str:
        """String representation."""
        return f"PhotoGrid({len(self._photos)} photos)"
