"""
Simple Thumbnail Widget for Library Views

A lightweight thumbnail display widget for use in Library views (Days, Months, Years).
Unlike PhotoTile which is coupled with the Photo model, this widget works with raw paths
and handles async thumbnail loading.

Date: 2025-10-20
Feature: Library View (002-library-view)
"""

from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont
from pathlib import Path


class ThumbnailWidget(QLabel):
    """
    Simple thumbnail widget for displaying photos with async loading support.

    This widget is simpler than PhotoTile and works directly with file paths,
    making it suitable for Library views that use LibraryItem instead of Photo.
    """

    # Signal emitted when thumbnail is clicked
    photo_clicked = pyqtSignal(Path)

    def __init__(self, source_path: Path, size: tuple[int, int], parent=None):
        """
        Initialize thumbnail widget.

        Args:
            source_path: Path to source image file
            size: Thumbnail size (width, height)
            parent: Parent widget
        """
        super().__init__(parent)

        self.source_path = source_path
        self.thumbnail_size = size

        # Configure widget
        self.setFixedSize(QSize(size[0], size[1]))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setScaledContents(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Set placeholder initially
        self._set_placeholder()

    def _set_placeholder(self):
        """Set placeholder image while thumbnail loads."""
        pixmap = QPixmap(self.thumbnail_size[0], self.thumbnail_size[1])
        pixmap.fill(QColor(220, 220, 220))

        # Draw loading indicator
        painter = QPainter(pixmap)
        painter.setPen(QColor(150, 150, 150))
        painter.setFont(QFont("Arial", 10))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Loading...")
        painter.end()

        self.setPixmap(pixmap)

    def set_thumbnail(self, pixmap: QPixmap):
        """
        Set the thumbnail pixmap.

        Args:
            pixmap: Thumbnail pixmap to display
        """
        # Scale pixmap to fit widget size while maintaining aspect ratio
        scaled = pixmap.scaled(
            self.thumbnail_size[0],
            self.thumbnail_size[1],
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.setPixmap(scaled)

    def show_error(self):
        """Show error state when thumbnail loading fails."""
        pixmap = QPixmap(self.thumbnail_size[0], self.thumbnail_size[1])
        pixmap.fill(QColor(200, 100, 100))

        # Draw error indicator
        painter = QPainter(pixmap)
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Arial", 12))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "⚠\nError")
        painter.end()

        self.setPixmap(pixmap)

    def mousePressEvent(self, event):
        """Handle mouse click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.photo_clicked.emit(self.source_path)
        super().mousePressEvent(event)
