"""PhotoTile widget for displaying individual photo thumbnails.

This widget is used within PhotoGrid to display photos in a tile-based layout.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont
from pathlib import Path
from typing import Optional

from ...models.photo import Photo, PhotoPair


class PhotoTile(QWidget):
    """Widget representing a single photo tile in the grid.

    Features:
    - Thumbnail display with loading placeholder
    - RAW+JPEG badge indicator
    - Selectable state with visual highlight
    - Click to open in lightbox
    - Hover state for better UX
    """

    # Signals
    clicked = pyqtSignal(object)  # Emits Photo or PhotoPair
    double_clicked = pyqtSignal(object)  # Emits Photo or PhotoPair
    selection_changed = pyqtSignal(bool)  # Emits new selected state

    def __init__(
        self,
        photo: Optional[Photo] = None,
        photo_pair: Optional[PhotoPair] = None,
        size: QSize = QSize(150, 150),
        parent=None
    ):
        """Initialize photo tile.

        Args:
            photo: Photo object to display (mutually exclusive with photo_pair)
            photo_pair: PhotoPair object to display (mutually exclusive with photo)
            size: Tile size
            parent: Parent widget
        """
        super().__init__(parent)

        # Store reference
        self.photo = photo
        self.photo_pair = photo_pair
        self.tile_size = size

        # State
        self._selected = False
        self._hovered = False
        self._thumbnail_loaded = False

        # Configure widget
        self.setFixedSize(size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)  # Enable hover events

        # Create UI
        self._create_widgets()

        # Load thumbnail
        self._load_thumbnail()

    def _create_widgets(self):
        """Create child widgets."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        # Thumbnail label
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setScaledContents(False)
        self.thumbnail_label.setMinimumSize(self.tile_size.width() - 8, self.tile_size.height() - 8)

        # Default placeholder
        self._set_placeholder()

        layout.addWidget(self.thumbnail_label)

    def _set_placeholder(self):
        """Set placeholder image while thumbnail loads."""
        pixmap = QPixmap(self.tile_size.width() - 8, self.tile_size.height() - 8)
        pixmap.fill(QColor(200, 200, 200))

        # Draw loading indicator
        painter = QPainter(pixmap)
        painter.setPen(QColor(150, 150, 150))
        painter.setFont(QFont("Arial", 10))
        painter.drawText(
            pixmap.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "Loading..."
        )
        painter.end()

        self.thumbnail_label.setPixmap(pixmap)

    def _load_thumbnail(self):
        """Load and display thumbnail."""
        thumbnail_path = self._get_thumbnail_path()

        if thumbnail_path and thumbnail_path.exists():
            self._display_thumbnail(thumbnail_path)
        else:
            # Thumbnail not yet generated - keep placeholder
            pass

    def _get_thumbnail_path(self) -> Optional[Path]:
        """Get thumbnail path from photo or photo pair.

        Returns:
            Path to thumbnail or None
        """
        if self.photo_pair:
            # For pairs, use JPEG for thumbnail
            photo = Photo(path=self.photo_pair.display_path)
            return photo.thumbnail_path
        elif self.photo:
            return self.photo.thumbnail_path
        return None

    def _display_thumbnail(self, thumbnail_path: Path):
        """Display thumbnail image.

        Args:
            thumbnail_path: Path to thumbnail file
        """
        pixmap = QPixmap(str(thumbnail_path))
        if not pixmap.isNull():
            # Scale to fit while maintaining aspect ratio
            scaled = pixmap.scaled(
                self.tile_size.width() - 8,
                self.tile_size.height() - 8,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.thumbnail_label.setPixmap(scaled)
            self._thumbnail_loaded = True

            # Draw RAW badge if this is a pair
            if self.photo_pair and self.photo_pair.has_raw:
                self._draw_raw_badge(scaled)

    def _draw_raw_badge(self, pixmap: QPixmap):
        """Draw RAW+JPEG badge on thumbnail.

        Args:
            pixmap: Pixmap to draw badge on
        """
        # Create a copy to draw on
        badged = QPixmap(pixmap.size())
        badged.fill(Qt.GlobalColor.transparent)

        painter = QPainter(badged)

        # Draw original pixmap
        painter.drawPixmap(0, 0, pixmap)

        # Draw badge in top-right corner
        badge_width = 45
        badge_height = 20
        margin = 5

        # Badge background
        badge_rect = badged.rect().adjusted(
            badged.width() - badge_width - margin,
            margin,
            -margin,
            -badged.height() + badge_height + margin
        )

        painter.fillRect(badge_rect, QColor(255, 140, 0, 200))  # Orange with transparency

        # Badge text
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        painter.drawText(
            badge_rect,
            Qt.AlignmentFlag.AlignCenter,
            "RAW"
        )

        painter.end()

        self.thumbnail_label.setPixmap(badged)

    def set_thumbnail(self, thumbnail_path: Path):
        """Set thumbnail from external source.

        Args:
            thumbnail_path: Path to thumbnail image
        """
        if self.photo:
            self.photo.thumbnail_path = thumbnail_path
        self._display_thumbnail(thumbnail_path)

    def get_photo_or_pair(self):
        """Get the photo or photo pair this tile represents.

        Returns:
            Photo or PhotoPair object
        """
        return self.photo_pair if self.photo_pair else self.photo

    def get_display_path(self) -> Optional[Path]:
        """Get the display path for this tile.

        Returns:
            Path to displayed image file
        """
        if self.photo_pair:
            return self.photo_pair.display_path
        elif self.photo:
            return self.photo.path
        return None

    def is_selected(self) -> bool:
        """Check if tile is selected.

        Returns:
            True if selected
        """
        return self._selected

    def set_selected(self, selected: bool):
        """Set selection state.

        Args:
            selected: Whether tile should be selected
        """
        if self._selected != selected:
            self._selected = selected
            self.update()  # Trigger repaint
            self.selection_changed.emit(selected)

    def toggle_selection(self):
        """Toggle selection state."""
        self.set_selected(not self._selected)

    def mousePressEvent(self, event):
        """Handle mouse press event.

        Args:
            event: Mouse event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.get_photo_or_pair())
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Handle mouse double-click event.

        Args:
            event: Mouse event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.get_photo_or_pair())
        super().mouseDoubleClickEvent(event)

    def enterEvent(self, event):
        """Handle mouse enter event.

        Args:
            event: Enter event
        """
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Handle mouse leave event.

        Args:
            event: Leave event
        """
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        """Custom paint event for selection highlight.

        Args:
            event: Paint event
        """
        super().paintEvent(event)

        # Draw selection or hover border
        if self._selected or self._hovered:
            painter = QPainter(self)

            if self._selected:
                # Blue selection border
                painter.setPen(QColor(30, 144, 255))  # Dodger blue
                painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
                painter.drawRect(self.rect().adjusted(1, 1, -2, -2))
            elif self._hovered:
                # Light gray hover border
                painter.setPen(QColor(150, 150, 150))
                painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

            painter.end()

    def __str__(self) -> str:
        """String representation."""
        if self.photo_pair:
            return f"PhotoTile(pair={self.photo_pair.base_name})"
        elif self.photo:
            return f"PhotoTile(photo={self.photo.filename})"
        return "PhotoTile(empty)"
