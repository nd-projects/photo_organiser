"""Album grid view for displaying albums in a tile-based layout.

Uses PyQt6's QListWidget in Icon mode for efficient rendering of large album collections.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from typing import Optional, Callable, List
from pathlib import Path

from ..models.album import Album


class AlbumGrid(QWidget):
    """Grid view for displaying photo albums.

    Features:
    - QListWidget in Icon mode for efficient grid rendering
    - Click to open album
    - Empty state message when no albums exist
    - Responsive grid layout with automatic wrapping
    """

    # Signal emitted when an album is clicked
    album_clicked = pyqtSignal(Album)

    def __init__(
        self,
        parent=None,
        on_album_click: Optional[Callable[[Album], None]] = None,
    ):
        """Initialize album grid view.

        Args:
            parent: Parent widget
            on_album_click: Callback when album is clicked (album) -> None
        """
        super().__init__(parent)

        self.on_album_click = on_album_click

        # State
        self._albums: List[Album] = []
        self._showing_empty_state = False

        # Create UI
        self._create_widgets()

        # Connect signal
        if self.on_album_click:
            self.album_clicked.connect(self.on_album_click)

    def _create_widgets(self):
        """Create child widgets."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # QListWidget in Icon mode for grid display
        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_widget.setIconSize(QSize(180, 180))
        self.list_widget.setSpacing(15)
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setMovement(QListWidget.Movement.Static)
        self.list_widget.setUniformItemSizes(True)  # Performance optimization
        self.list_widget.setWordWrap(True)

        # Enable grid flow
        self.list_widget.setFlow(QListWidget.Flow.LeftToRight)
        self.list_widget.setWrapping(True)

        # Connect item click
        self.list_widget.itemClicked.connect(self._handle_item_click)

        layout.addWidget(self.list_widget)

        # Empty state label (hidden by default)
        self.empty_label = QLabel(
            "No albums found\n\nAdd photo albums to your photo directory to get started."
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
        # Get album from item data
        album = item.data(Qt.ItemDataRole.UserRole)
        if album:
            self.album_clicked.emit(album)

    def set_albums(self, albums: List[Album]):
        """Set albums to display in the grid.

        Args:
            albums: List of albums to display
        """
        self._albums = albums

        if len(albums) == 0:
            self._show_empty_state()
        else:
            self._hide_empty_state()
            self._populate_list(albums)

    def _populate_list(self, albums: List[Album]):
        """Populate the list widget with album items.

        Args:
            albums: List of albums to display
        """
        self.list_widget.clear()

        for album in albums:
            item = QListWidgetItem()

            # Set album data
            item.setData(Qt.ItemDataRole.UserRole, album)

            # Set text (album name and date)
            text = album.name
            if album.date:
                text += f"\n{album.date_string}"
            else:
                text += "\nUnknown Date"
            text += f"\n{album.photo_count} photos"
            item.setText(text)

            # Set icon/thumbnail
            if album.thumbnail_path and album.thumbnail_path.exists():
                pixmap = QPixmap(str(album.thumbnail_path))
                if not pixmap.isNull():
                    # Scale to fit icon size while maintaining aspect ratio
                    scaled = pixmap.scaled(
                        180, 180,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    item.setIcon(QIcon(scaled))
                else:
                    item.setIcon(QIcon(self._create_error_pixmap()))
            else:
                # Placeholder
                item.setIcon(QIcon(self._create_placeholder_pixmap()))

            # Set size hint
            item.setSizeHint(QSize(200, 240))

            self.list_widget.addItem(item)

    def get_albums(self) -> List[Album]:
        """Get currently displayed albums.

        Returns:
            List of albums
        """
        return self._albums.copy()

    def clear(self):
        """Clear all albums from the grid."""
        self._albums.clear()
        self.list_widget.clear()
        self._show_empty_state()

    def refresh(self):
        """Refresh the grid display."""
        if len(self._albums) > 0:
            self._populate_list(self._albums)

    def refresh_album(self, album: Album):
        """Refresh a specific album tile.

        Args:
            album: Album to refresh
        """
        # Find album index and update its item
        try:
            idx = self._albums.index(album)
            item = self.list_widget.item(idx)
            if item:
                # Update text
                text = album.name
                if album.date:
                    text += f"\n{album.date_string}"
                else:
                    text += "\nUnknown Date"
                text += f"\n{album.photo_count} photos"
                item.setText(text)

                # Update album data
                item.setData(Qt.ItemDataRole.UserRole, album)
        except ValueError:
            pass  # Album not in list

    def scroll_to_top(self):
        """Scroll to the top of the grid."""
        self.list_widget.scrollToTop()

    def scroll_to_album(self, album: Album):
        """Scroll to show a specific album.

        Args:
            album: Album to scroll to
        """
        try:
            idx = self._albums.index(album)
            item = self.list_widget.item(idx)
            if item:
                self.list_widget.scrollToItem(item)
        except ValueError:
            pass  # Album not in list

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

    def get_album_count(self) -> int:
        """Get count of albums in the grid.

        Returns:
            Number of albums
        """
        return len(self._albums)

    def find_album_by_path(self, path: Path) -> Optional[Album]:
        """Find album by its path.

        Args:
            path: Path to album directory

        Returns:
            Album if found, None otherwise
        """
        for album in self._albums:
            if album.path == path:
                return album
        return None

    def add_album(self, album: Album, position: Optional[int] = None):
        """Add a new album to the grid.

        Args:
            album: Album to add
            position: Optional position to insert at (defaults to end)
        """
        if position is None:
            self._albums.append(album)
        else:
            self._albums.insert(position, album)

        self.set_albums(self._albums)

    def remove_album(self, album: Album):
        """Remove an album from the grid.

        Args:
            album: Album to remove
        """
        try:
            self._albums.remove(album)
            self.set_albums(self._albums)
        except ValueError:
            pass  # Album not in list

    def sort_albums(self, key_func: Callable[[Album], any], reverse: bool = False):
        """Sort albums by a key function.

        Args:
            key_func: Function to extract sort key from album
            reverse: Whether to sort in reverse order
        """
        self._albums.sort(key=key_func, reverse=reverse)
        self.set_albums(self._albums)

    def sort_by_date(self, newest_first: bool = True):
        """Sort albums by date.

        Args:
            newest_first: Whether to show newest albums first
        """
        import datetime
        # Sort by date, putting None dates at the end
        self._albums.sort(
            key=lambda a: a.date if a.date else (
                datetime.date.min if newest_first else datetime.date.max
            ),
            reverse=newest_first
        )
        self.set_albums(self._albums)

    def sort_by_name(self, ascending: bool = True):
        """Sort albums by name.

        Args:
            ascending: Whether to sort in ascending order
        """
        self._albums.sort(key=lambda a: a.name.lower(), reverse=not ascending)
        self.set_albums(self._albums)

    def filter_albums(self, filter_func: Callable[[Album], bool]):
        """Filter albums by a predicate function.

        Args:
            filter_func: Function that returns True for albums to keep
        """
        filtered = [album for album in self._albums if filter_func(album)]
        self.set_albums(filtered)

    def _create_placeholder_pixmap(self) -> QPixmap:
        """Create placeholder pixmap for loading state.

        Returns:
            Placeholder pixmap
        """
        from PyQt6.QtGui import QColor, QPainter, QFont

        pixmap = QPixmap(180, 180)
        pixmap.fill(QColor(220, 220, 220))

        painter = QPainter(pixmap)
        painter.setPen(QColor(150, 150, 150))
        painter.setFont(QFont("Arial", 10))
        painter.drawText(
            pixmap.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "No Photos"
        )
        painter.end()

        return pixmap

    def _create_error_pixmap(self) -> QPixmap:
        """Create error pixmap for failed loads.

        Returns:
            Error pixmap
        """
        from PyQt6.QtGui import QColor, QPainter, QFont

        pixmap = QPixmap(180, 180)
        pixmap.fill(QColor(200, 100, 100))

        painter = QPainter(pixmap)
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Arial", 10))
        painter.drawText(
            pixmap.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "⚠\nError"
        )
        painter.end()

        return pixmap

    def __str__(self) -> str:
        """String representation."""
        return f"AlbumGrid({len(self._albums)} albums)"
