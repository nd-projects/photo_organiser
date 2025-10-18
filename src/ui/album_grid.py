"""Album grid view for displaying albums in a tile-based layout.

Uses PyQt6's QListWidget in Icon mode for efficient rendering of large album collections.
Supports drag-and-drop reordering of albums.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel,
    QPushButton, QHBoxLayout, QMessageBox
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QPoint, QTimer, QRect
from PyQt6.QtGui import QIcon, QPixmap, QDragEnterEvent, QDropEvent, QDragMoveEvent, QPainter, QColor, QPen
from typing import Optional, Callable, List
from pathlib import Path

from ..models.album import Album
from .widgets.drag_drop import DragDropHelper


class AlbumListWidget(QListWidget):
    """Custom QListWidget with enhanced drag-drop visual feedback.

    Shows a full-size ghost placeholder when dragging to show where the album will be dropped.
    The ghost pushes other albums aside for accurate visual feedback.
    """

    # Signal emitted when a drop is completed successfully
    drop_completed = pyqtSignal()

    def __init__(self, parent=None):
        """Initialize custom list widget."""
        super().__init__(parent)
        self._ghost_item: Optional[QListWidgetItem] = None
        self._dragged_item: Optional[QListWidgetItem] = None
        self._source_index: Optional[int] = None

    def startDrag(self, supportedActions):
        """Override to track which item is being dragged and create ghost.

        Args:
            supportedActions: Supported drag actions
        """
        # Store the dragged item and its index
        self._dragged_item = self.currentItem()
        if self._dragged_item:
            self._source_index = self.row(self._dragged_item)

            # Make the original item semi-transparent while dragging
            # This creates the effect of it being "lifted"
            icon = self._dragged_item.icon()
            if not icon.isNull():
                # We'll handle the transparency in the drag pixmap instead
                pass

        super().startDrag(supportedActions)

    def dragMoveEvent(self, event: QDragMoveEvent):
        """Handle drag move to show ghost placeholder.

        Args:
            event: Drag move event
        """
        # Accept the event first
        event.accept()

        # Find the item at the drop position
        drop_pos = event.position().toPoint()
        target_item = self.itemAt(drop_pos)

        # Calculate target index
        if target_item:
            target_index = self.row(target_item)

            # Check if drop is in left or right half of item
            item_rect = self.visualItemRect(target_item)
            relative_x = drop_pos.x() - item_rect.x()
            drop_before = relative_x < item_rect.width() / 2

            if not drop_before:
                target_index += 1
        else:
            # Dropping in empty space - target is at end
            target_index = self.count()

        # Adjust target if we have a ghost item already
        if self._ghost_item:
            ghost_index = self.row(self._ghost_item)

            # If target hasn't changed, no need to update
            if ghost_index == target_index:
                return

            # Remove the old ghost
            self.takeItem(ghost_index)
            self._ghost_item = None

            # Adjust target index if needed
            if target_index > ghost_index:
                target_index -= 1

        # Don't create ghost at the source position
        if target_index == self._source_index:
            return

        # Create and insert ghost item
        self._ghost_item = self._create_ghost_item()
        self.insertItem(target_index, self._ghost_item)

    def dragLeaveEvent(self, event):
        """Handle drag leave to remove ghost.

        Args:
            event: Drag leave event
        """
        self._remove_ghost()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent):
        """Handle drop event with proper position calculation.

        Args:
            event: Drop event
        """
        print(f"DEBUG: dropEvent called")
        print(f"  Ghost item exists: {self._ghost_item is not None}")
        print(f"  Dragged item exists: {self._dragged_item is not None}")
        print(f"  Source index: {self._source_index}")

        # Find where the ghost is (this is where we want to drop)
        target_index = None
        if self._ghost_item:
            target_index = self.row(self._ghost_item)
            print(f"  Ghost at index: {target_index}")

        if target_index is not None and self._dragged_item is not None and self._source_index is not None:
            # Store the dragged item data before any operations
            source_index = self._source_index

            # Remove the ghost first
            print(f"  Removing ghost...")
            self._remove_ghost()

            # Adjust target index since we removed the ghost
            if target_index > source_index:
                # Ghost was after source, so target moves back by 1
                target_index -= 1
                print(f"  Adjusted target index to: {target_index}")

            print(f"  Moving item from {source_index} to {target_index}")

            # Only move if actually changing position
            if source_index != target_index:
                # Verify the item still exists at source index
                if source_index < self.count():
                    # Take the item from its current position
                    taken_item = self.takeItem(source_index)
                    album = taken_item.data(Qt.ItemDataRole.UserRole) if taken_item else None
                    print(f"  Took item: {taken_item is not None}, album: {album.name if album else 'None'}")

                    if taken_item:
                        # Verify the album data is still attached
                        if not album:
                            print(f"  ERROR: Taken item has no album data!")

                        # Insert at the target position
                        self.insertItem(target_index, taken_item)
                        print(f"  Inserted at {target_index}")

                        # Verify after insertion
                        verify_item = self.item(target_index)
                        verify_album = verify_item.data(Qt.ItemDataRole.UserRole) if verify_item else None
                        print(f"  Verify: item at {target_index} has album: {verify_album.name if verify_album else 'None'}")

                        # Select the moved item
                        self.setCurrentItem(taken_item)
                        print(f"  Item moved successfully")

                        # Emit signal that drop completed
                        self.drop_completed.emit()
                    else:
                        print(f"  ERROR: Failed to take item at index {source_index}")
                else:
                    print(f"  ERROR: Source index {source_index} out of range (count: {self.count()})")
            else:
                print(f"  No move needed - same position")

            # Accept the event to prevent default handling
            event.accept()
        else:
            print(f"  Cannot drop - missing required data")
            # Remove ghost if present
            self._remove_ghost()
            # Accept but don't do anything
            event.accept()

        # Clear state
        self._dragged_item = None
        self._source_index = None
        print(f"  State cleared")

    def _create_ghost_item(self) -> QListWidgetItem:
        """Create a ghost placeholder item.

        Returns:
            Ghost item
        """
        ghost = QListWidgetItem()

        # Copy properties from dragged item if available
        if self._dragged_item:
            ghost.setSizeHint(self._dragged_item.sizeHint())
            ghost.setText("")  # No text for ghost

            # IMPORTANT: Do NOT copy album data to ghost!
            # Ghost should have NO UserRole data so it's not counted as a real album
            print(f"  Creating ghost (no album data)")

            # Create a semi-transparent ghost icon
            original_icon = self._dragged_item.icon()
            if not original_icon.isNull():
                # Get the icon pixmap
                pixmap = original_icon.pixmap(self.iconSize())

                # Create ghost version (semi-transparent with dashed border)
                ghost_pixmap = QPixmap(pixmap.size())
                ghost_pixmap.fill(Qt.GlobalColor.transparent)

                painter = QPainter(ghost_pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)

                # Draw semi-transparent version of original
                painter.setOpacity(0.3)
                painter.drawPixmap(0, 0, pixmap)

                # Draw dashed border
                painter.setOpacity(1.0)
                painter.setPen(QPen(QColor(70, 130, 220), 2, Qt.PenStyle.DashLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(ghost_pixmap.rect().adjusted(1, 1, -1, -1), 5, 5)

                painter.end()

                ghost.setIcon(QIcon(ghost_pixmap))
            else:
                # Create a placeholder ghost if no icon
                placeholder = self._create_ghost_placeholder()
                ghost.setIcon(QIcon(placeholder))
        else:
            # Fallback size
            ghost.setSizeHint(QSize(200, 240))
            placeholder = self._create_ghost_placeholder()
            ghost.setIcon(QIcon(placeholder))

        # Make it non-selectable
        ghost.setFlags(Qt.ItemFlag.NoItemFlags)

        print(f"  Ghost created with data: {ghost.data(Qt.ItemDataRole.UserRole)}")
        return ghost

    def _create_ghost_placeholder(self) -> QPixmap:
        """Create a placeholder pixmap for ghost.

        Returns:
            Ghost placeholder pixmap
        """
        pixmap = QPixmap(self.iconSize())
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw dashed rectangle
        painter.setPen(QPen(QColor(70, 130, 220), 2, Qt.PenStyle.DashLine))
        painter.setBrush(QColor(70, 130, 220, 30))
        painter.drawRoundedRect(pixmap.rect().adjusted(5, 5, -5, -5), 5, 5)

        painter.end()
        return pixmap

    def _remove_ghost(self):
        """Remove the ghost item if it exists."""
        if self._ghost_item:
            row = self.row(self._ghost_item)
            print(f"  Removing ghost at row: {row}")
            if row >= 0:
                removed = self.takeItem(row)
                print(f"  Ghost removed: {removed is not None}")
            else:
                print(f"  Ghost row invalid: {row}")
            self._ghost_item = None
        else:
            print(f"  No ghost to remove")


class AlbumGrid(QWidget):
    """Grid view for displaying photo albums.

    Features:
    - QListWidget in Icon mode for efficient grid rendering
    - Click to open album
    - Drag-and-drop reordering of albums
    - Empty state message when no albums exist
    - Responsive grid layout with automatic wrapping
    """

    # Signal emitted when an album is clicked
    album_clicked = pyqtSignal(Album)

    # Signal emitted when albums are reordered via drag-drop
    albums_reordered = pyqtSignal(list)  # Emits new album order

    # Signal emitted when user requests to revert to chronological order
    revert_to_chronological_requested = pyqtSignal()

    def __init__(
        self,
        parent=None,
        on_album_click: Optional[Callable[[Album], None]] = None,
        enable_drag_drop: bool = True,
    ):
        """Initialize album grid view.

        Args:
            parent: Parent widget
            on_album_click: Callback when album is clicked (album) -> None
            enable_drag_drop: Whether to enable drag-drop reordering
        """
        super().__init__(parent)

        self.on_album_click = on_album_click
        self._drag_drop_enabled = enable_drag_drop

        # State
        self._albums: List[Album] = []
        self._showing_empty_state = False
        self._drag_start_position: Optional[QPoint] = None

        # Create UI
        self._create_widgets()

        # Connect signal
        if self.on_album_click:
            self.album_clicked.connect(self.on_album_click)

    def _create_widgets(self):
        """Create child widgets."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Add toolbar with revert button
        if self._drag_drop_enabled:
            toolbar_layout = QHBoxLayout()
            toolbar_layout.setContentsMargins(10, 5, 10, 5)

            # Revert to chronological button
            self.revert_button = QPushButton("↻ Reset to Chronological Order")
            self.revert_button.setToolTip("Revert custom ordering and sort by date")
            self.revert_button.clicked.connect(self._handle_revert_to_chronological)
            toolbar_layout.addWidget(self.revert_button)

            toolbar_layout.addStretch()
            layout.addLayout(toolbar_layout)

        # Custom QListWidget in Icon mode for grid display with enhanced drag-drop
        self.list_widget = AlbumListWidget()
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_widget.setIconSize(QSize(180, 180))
        self.list_widget.setSpacing(15)
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        # Use Snap movement to allow drag-drop while maintaining grid alignment
        self.list_widget.setMovement(QListWidget.Movement.Snap)
        self.list_widget.setUniformItemSizes(True)  # Performance optimization
        self.list_widget.setWordWrap(True)

        # Enable grid flow
        self.list_widget.setFlow(QListWidget.Flow.LeftToRight)
        self.list_widget.setWrapping(True)

        # Enable drag-drop if requested
        if self._drag_drop_enabled:
            self.list_widget.setDragEnabled(True)
            self.list_widget.setAcceptDrops(True)
            self.list_widget.setDropIndicatorShown(True)
            self.list_widget.setDragDropMode(QListWidget.DragDropMode.InternalMove)
            self.list_widget.setDefaultDropAction(Qt.DropAction.MoveAction)

            # Block the rowsMoved signal to prevent Qt's internal handling from interfering
            # We handle everything in our custom dropEvent
            try:
                self.list_widget.model().rowsMoved.disconnect()
            except:
                pass  # No connections to disconnect

            # Connect to our custom drop_completed signal
            # This is emitted from AlbumListWidget.dropEvent after successful move
            # Call immediately (no timer) to ensure we read the list before anything else modifies it
            self.list_widget.drop_completed.connect(self._handle_drop_complete)

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

    def _handle_drop_complete(self):
        """Handle completion of drag-drop operation.

        Extracts the new album order from the list widget and emits signal.
        """
        print(f"DEBUG: _handle_drop_complete called")
        print(f"DEBUG: List widget count: {self.list_widget.count()}")

        # Rebuild album list from current item order
        new_order = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item:
                album = item.data(Qt.ItemDataRole.UserRole)
                print(f"  Position {i}: item exists, album={album.name if album else 'None'}")
                # Only add if it's a real album (not a ghost)
                if album:
                    new_order.append(album)
            else:
                print(f"  Position {i}: item is None!")

        # Update internal list
        self._albums = new_order

        print(f"DEBUG: Emitting albums_reordered signal with {len(new_order)} albums")
        # Emit signal with new order
        self.albums_reordered.emit(new_order)

    def _handle_revert_to_chronological(self):
        """Handle revert to chronological order button click."""
        # Ask for confirmation
        reply = QMessageBox.question(
            self,
            "Revert to Chronological Order",
            "This will reset the album order to chronological (newest first). Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.revert_to_chronological_requested.emit()

    def set_drag_drop_enabled(self, enabled: bool):
        """Enable or disable drag-drop functionality.

        Args:
            enabled: Whether to enable drag-drop
        """
        self._drag_drop_enabled = enabled

        if enabled:
            self.list_widget.setDragEnabled(True)
            self.list_widget.setAcceptDrops(True)
            self.list_widget.setDropIndicatorShown(True)
            self.list_widget.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        else:
            self.list_widget.setDragEnabled(False)
            self.list_widget.setAcceptDrops(False)
            self.list_widget.setDropIndicatorShown(False)
            self.list_widget.setDragDropMode(QListWidget.DragDropMode.NoDragDrop)

    def is_drag_drop_enabled(self) -> bool:
        """Check if drag-drop is enabled.

        Returns:
            True if drag-drop is enabled
        """
        return self._drag_drop_enabled

    def __str__(self) -> str:
        """String representation."""
        return f"AlbumGrid({len(self._albums)} albums)"
