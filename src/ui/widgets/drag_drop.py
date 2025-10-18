"""Drag and drop utilities for album reordering.

Provides helper functions and classes for implementing drag-and-drop functionality
in the album grid view.
"""

from PyQt6.QtCore import Qt, QMimeData, QPoint
from PyQt6.QtGui import QDrag, QPixmap, QPainter, QColor
from PyQt6.QtWidgets import QWidget, QListWidgetItem
from typing import Optional


class DragDropHelper:
    """Helper class for drag-and-drop operations."""

    # MIME type for album drag-drop
    ALBUM_MIME_TYPE = "application/x-photo-organizer-album"

    @staticmethod
    def create_album_drag(
        widget: QWidget,
        item: QListWidgetItem,
        album_path: str,
        preview_pixmap: Optional[QPixmap] = None
    ) -> QDrag:
        """Create a QDrag object for an album item.

        Args:
            widget: Source widget initiating the drag
            item: List widget item being dragged
            album_path: Path to the album being dragged
            preview_pixmap: Optional pixmap for drag preview

        Returns:
            Configured QDrag object
        """
        drag = QDrag(widget)

        # Create MIME data
        mime_data = QMimeData()
        mime_data.setData(DragDropHelper.ALBUM_MIME_TYPE, album_path.encode('utf-8'))
        mime_data.setText(album_path)
        drag.setMimeData(mime_data)

        # Set drag preview pixmap
        if preview_pixmap and not preview_pixmap.isNull():
            # Scale preview to reasonable size
            scaled_preview = preview_pixmap.scaled(
                200, 200,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            # Add semi-transparent background
            final_pixmap = DragDropHelper._add_drag_shadow(scaled_preview)
            drag.setPixmap(final_pixmap)
            drag.setHotSpot(QPoint(final_pixmap.width() // 2, final_pixmap.height() // 2))
        else:
            # Create a simple placeholder preview
            placeholder = DragDropHelper._create_placeholder_preview(item.text())
            drag.setPixmap(placeholder)
            drag.setHotSpot(QPoint(placeholder.width() // 2, placeholder.height() // 2))

        return drag

    @staticmethod
    def _add_drag_shadow(pixmap: QPixmap) -> QPixmap:
        """Add semi-transparent shadow effect to drag preview.

        Args:
            pixmap: Original pixmap

        Returns:
            Pixmap with shadow effect
        """
        # Create a slightly larger pixmap for shadow
        result = QPixmap(pixmap.width() + 10, pixmap.height() + 10)
        result.fill(Qt.GlobalColor.transparent)

        painter = QPainter(result)

        # Draw shadow (dark, semi-transparent)
        painter.setOpacity(0.3)
        painter.setBrush(QColor(0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(5, 5, pixmap.width(), pixmap.height(), 5, 5)

        # Draw original image with slight transparency
        painter.setOpacity(0.85)
        painter.drawPixmap(0, 0, pixmap)

        painter.end()

        return result

    @staticmethod
    def _create_placeholder_preview(text: str) -> QPixmap:
        """Create a simple text-based drag preview.

        Args:
            text: Text to display (e.g., album name)

        Returns:
            Placeholder preview pixmap
        """
        from PyQt6.QtGui import QFont, QFontMetrics

        # Create pixmap with text
        font = QFont("Arial", 12, QFont.Weight.Bold)
        metrics = QFontMetrics(font)

        # Limit text length
        display_text = text[:30] + "..." if len(text) > 30 else text
        text_width = metrics.horizontalAdvance(display_text)
        text_height = metrics.height()

        pixmap = QPixmap(text_width + 40, text_height + 30)
        pixmap.fill(QColor(240, 240, 240, 230))

        painter = QPainter(pixmap)
        painter.setFont(font)
        painter.setPen(QColor(60, 60, 60))

        # Draw rounded background
        painter.setBrush(QColor(255, 255, 255, 200))
        painter.drawRoundedRect(5, 5, pixmap.width() - 10, pixmap.height() - 10, 10, 10)

        # Draw text centered
        painter.drawText(
            pixmap.rect(),
            Qt.AlignmentFlag.AlignCenter,
            display_text
        )

        painter.end()

        return pixmap

    @staticmethod
    def extract_album_path_from_mime(mime_data: QMimeData) -> Optional[str]:
        """Extract album path from MIME data.

        Args:
            mime_data: MIME data from drag event

        Returns:
            Album path string, or None if not found
        """
        if mime_data.hasFormat(DragDropHelper.ALBUM_MIME_TYPE):
            data = mime_data.data(DragDropHelper.ALBUM_MIME_TYPE)
            return bytes(data).decode('utf-8')

        return None

    @staticmethod
    def is_album_drag(mime_data: QMimeData) -> bool:
        """Check if MIME data contains album drag data.

        Args:
            mime_data: MIME data to check

        Returns:
            True if this is an album drag operation
        """
        return mime_data.hasFormat(DragDropHelper.ALBUM_MIME_TYPE)


class DropIndicator:
    """Helper for drawing drop position indicators."""

    @staticmethod
    def draw_insertion_line(
        painter: QPainter,
        x: int,
        y: int,
        width: int,
        is_horizontal: bool = True
    ):
        """Draw an insertion line indicator.

        Args:
            painter: QPainter to draw with
            x: X coordinate
            y: Y coordinate
            width: Line width
            is_horizontal: Whether to draw horizontal line
        """
        from PyQt6.QtGui import QPen

        # Blue insertion line
        pen = QPen(QColor(70, 130, 220), 3, Qt.PenStyle.SolidLine)
        painter.setPen(pen)

        if is_horizontal:
            painter.drawLine(x, y, x + width, y)

            # Draw arrows at ends
            arrow_size = 8
            painter.drawLine(x, y, x + arrow_size, y - arrow_size // 2)
            painter.drawLine(x, y, x + arrow_size, y + arrow_size // 2)
            painter.drawLine(x + width, y, x + width - arrow_size, y - arrow_size // 2)
            painter.drawLine(x + width, y, x + width - arrow_size, y + arrow_size // 2)
        else:
            # Vertical line
            painter.drawLine(x, y, x, y + width)

            # Draw arrows at ends
            arrow_size = 8
            painter.drawLine(x, y, x - arrow_size // 2, y + arrow_size)
            painter.drawLine(x, y, x + arrow_size // 2, y + arrow_size)
            painter.drawLine(x, y + width, x - arrow_size // 2, y + width - arrow_size)
            painter.drawLine(x, y + width, x + arrow_size // 2, y + width - arrow_size)

    @staticmethod
    def highlight_drop_target(painter: QPainter, rect, color: QColor = None):
        """Highlight a drop target area.

        Args:
            painter: QPainter to draw with
            rect: Rectangle to highlight
            color: Optional highlight color (default: semi-transparent blue)
        """
        from PyQt6.QtGui import QPen

        if color is None:
            color = QColor(70, 130, 220, 100)

        painter.setBrush(color)
        pen = QPen(QColor(70, 130, 220), 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)

        painter.drawRoundedRect(rect, 5, 5)
