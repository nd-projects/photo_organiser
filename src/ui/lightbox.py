"""Lightbox modal for full-size photo viewing.

Provides a modal dialog for viewing photos at full resolution with
navigation controls and keyboard shortcuts.
"""

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QKeyEvent
from pathlib import Path
from typing import Optional, List

from ..models.photo import Photo, PhotoPair


class Lightbox(QDialog):
    """Modal dialog for viewing photos at full size.

    Features:
    - Full-size photo display with scrolling
    - Previous/Next navigation
    - Keyboard shortcuts (arrows, Escape)
    - Photo info display (filename, dimensions)
    - Handles both Photo and PhotoPair objects
    - Error handling for corrupted images
    """

    # Signals
    closed = pyqtSignal()
    photo_changed = pyqtSignal(int)  # Emits new photo index

    def __init__(
        self,
        photos: List,  # List[Photo | PhotoPair]
        current_index: int = 0,
        parent=None,
    ):
        """Initialize lightbox.

        Args:
            photos: List of Photo or PhotoPair objects
            current_index: Index of photo to display initially
            parent: Parent widget
        """
        super().__init__(parent)

        self.photos = photos
        self.current_index = current_index

        # State
        self._image_loaded = False
        self._error_state = False
        self._original_pixmap: Optional[QPixmap] = None

        # Configure dialog
        self.setWindowTitle("Photo Viewer")
        self.setModal(True)
        self.setMinimumSize(800, 600)

        # Full screen mode support
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )

        # Create UI
        self._create_widgets()
        self._setup_shortcuts()

        # Load initial photo (delayed to allow proper sizing)
        QTimer.singleShot(0, self._load_current_photo)

    def _create_widgets(self):
        """Create child widgets."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top toolbar
        self._create_toolbar(layout)

        # Photo display area with scroll
        self.scroll_area = QScrollArea()
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setStyleSheet("background-color: #1a1a1a;")

        self.photo_label = QLabel()
        self.photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photo_label.setStyleSheet("background-color: #1a1a1a;")
        self.photo_label.setScaledContents(False)

        self.scroll_area.setWidget(self.photo_label)
        layout.addWidget(self.scroll_area, stretch=1)

        # Bottom info bar
        self._create_info_bar(layout)

        # Navigation buttons
        self._create_navigation(layout)

    def _create_toolbar(self, parent_layout):
        """Create top toolbar.

        Args:
            parent_layout: Parent layout to add toolbar to
        """
        toolbar = QWidget()
        toolbar.setStyleSheet("background-color: #2a2a2a; padding: 5px;")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(10, 5, 10, 5)

        # Title label
        self.title_label = QLabel("Photo Viewer")
        self.title_label.setStyleSheet(
            "color: white; font-size: 14px; font-weight: bold;"
        )
        toolbar_layout.addWidget(self.title_label)

        toolbar_layout.addStretch()

        # Close button
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
        """)
        close_btn.clicked.connect(self.close)
        toolbar_layout.addWidget(close_btn)

        parent_layout.addWidget(toolbar)

    def _create_info_bar(self, parent_layout):
        """Create bottom info bar.

        Args:
            parent_layout: Parent layout to add info bar to
        """
        info_widget = QWidget()
        info_widget.setStyleSheet("background-color: #2a2a2a; padding: 5px;")
        info_layout = QHBoxLayout(info_widget)
        info_layout.setContentsMargins(10, 5, 10, 5)

        self.info_label = QLabel()
        self.info_label.setStyleSheet("color: white; font-size: 12px;")
        info_layout.addWidget(self.info_label)

        info_layout.addStretch()

        # Counter (e.g., "3 / 15")
        self.counter_label = QLabel()
        self.counter_label.setStyleSheet("color: white; font-size: 12px;")
        info_layout.addWidget(self.counter_label)

        parent_layout.addWidget(info_widget)

    def _create_navigation(self, parent_layout):
        """Create navigation controls.

        Args:
            parent_layout: Parent layout to add navigation to
        """
        nav_widget = QWidget()
        nav_widget.setStyleSheet("background-color: #2a2a2a; padding: 10px;")
        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(10, 10, 10, 10)

        nav_layout.addStretch()

        # Previous button
        self.prev_btn = QPushButton("← Previous")
        self.prev_btn.setFixedHeight(35)
        self.prev_btn.setStyleSheet(self._get_button_style())
        self.prev_btn.clicked.connect(self.show_previous)
        nav_layout.addWidget(self.prev_btn)

        # Next button
        self.next_btn = QPushButton("Next →")
        self.next_btn.setFixedHeight(35)
        self.next_btn.setStyleSheet(self._get_button_style())
        self.next_btn.clicked.connect(self.show_next)
        nav_layout.addWidget(self.next_btn)

        nav_layout.addStretch()

        parent_layout.addWidget(nav_widget)

        # Update button states
        self._update_navigation_buttons()

    def _get_button_style(self) -> str:
        """Get button stylesheet.

        Returns:
            CSS stylesheet for buttons
        """
        return """
            QPushButton {
                background-color: #4a4a4a;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
            QPushButton:pressed {
                background-color: #3a3a3a;
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #666;
            }
        """

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Note: keyPressEvent handles shortcuts
        pass

    def _load_current_photo(self):
        """Load and display the current photo."""
        if (
            not self.photos
            or self.current_index < 0
            or self.current_index >= len(self.photos)
        ):
            self._show_error("No photo to display")
            return

        photo_or_pair = self.photos[self.current_index]
        display_path = self._get_display_path(photo_or_pair)

        if not display_path or not display_path.exists():
            self._show_error(f"Photo not found: {display_path}")
            return

        # Load image
        try:
            pixmap = QPixmap(str(display_path))
            if pixmap.isNull():
                self._show_error("Failed to load image")
                return

            # Store original pixmap for resizing
            self._original_pixmap = pixmap

            # Scale and display image
            self._scale_and_display_image()

            self._image_loaded = True
            self._error_state = False

            # Update UI (use original pixmap for dimensions)
            self._update_title(photo_or_pair)
            self._update_info(photo_or_pair, pixmap)
            self._update_counter()
            self._update_navigation_buttons()

        except Exception as e:
            self._show_error(f"Error loading image: {e}")

    def _scale_and_display_image(self):
        """Scale the current image to fit the available space."""
        if not self._original_pixmap:
            return

        # Get available space
        available_size = self.scroll_area.size()

        # Account for margins and ensure minimum size
        available_width = max(available_size.width() - 20, 100)
        available_height = max(available_size.height() - 20, 100)

        # Scale image to fit while maintaining aspect ratio
        scaled_pixmap = self._original_pixmap.scaled(
            available_width,
            available_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        # Display scaled image
        self.photo_label.setPixmap(scaled_pixmap)
        self.photo_label.adjustSize()

    def _get_display_path(self, photo_or_pair) -> Optional[Path]:
        """Get display path from Photo or PhotoPair.

        Args:
            photo_or_pair: Photo or PhotoPair object

        Returns:
            Path to display or None
        """
        if isinstance(photo_or_pair, PhotoPair):
            return photo_or_pair.display_path
        elif isinstance(photo_or_pair, Photo):
            return photo_or_pair.path
        return None

    def _update_title(self, photo_or_pair):
        """Update title bar with photo name.

        Args:
            photo_or_pair: Photo or PhotoPair object
        """
        display_path = self._get_display_path(photo_or_pair)
        if display_path:
            filename = display_path.name

            # Add RAW indicator for pairs
            if isinstance(photo_or_pair, PhotoPair) and photo_or_pair.has_raw:
                filename += " (RAW+JPEG)"

            self.title_label.setText(filename)

    def _update_info(self, photo_or_pair, pixmap: QPixmap):
        """Update info bar with photo details.

        Args:
            photo_or_pair: Photo or PhotoPair object
            pixmap: Loaded pixmap for dimension info
        """
        display_path = self._get_display_path(photo_or_pair)
        if not display_path:
            return

        # Get dimensions
        width = pixmap.width()
        height = pixmap.height()

        # Get file size
        try:
            size_bytes = display_path.stat().st_size
            size_mb = size_bytes / (1024 * 1024)
            size_str = (
                f"{size_mb:.1f} MB" if size_mb >= 1 else f"{size_bytes // 1024} KB"
            )
        except OSError:
            size_str = "Unknown size"

        # Format info
        info_text = f"{width} × {height} • {size_str}"

        self.info_label.setText(info_text)

    def _update_counter(self):
        """Update photo counter display."""
        total = len(self.photos)
        current = self.current_index + 1
        self.counter_label.setText(f"{current} / {total}")

    def _update_navigation_buttons(self):
        """Update navigation button enabled states."""
        self.prev_btn.setEnabled(self.current_index > 0)
        self.next_btn.setEnabled(self.current_index < len(self.photos) - 1)

    def _show_error(self, message: str):
        """Show error message in place of photo.

        Args:
            message: Error message to display
        """
        self._error_state = True
        self._image_loaded = False

        # Create error pixmap
        error_pixmap = QPixmap(400, 300)
        error_pixmap.fill(Qt.GlobalColor.darkGray)

        from PyQt6.QtGui import QPainter, QFont, QColor

        painter = QPainter(error_pixmap)
        painter.setPen(QColor(255, 100, 100))
        painter.setFont(QFont("Arial", 12))
        painter.drawText(
            error_pixmap.rect(), Qt.AlignmentFlag.AlignCenter, f"⚠\n\n{message}"
        )
        painter.end()

        self.photo_label.setPixmap(error_pixmap)
        self.photo_label.adjustSize()

        self.info_label.setText("Error")
        self._update_counter()

    def show_previous(self):
        """Show previous photo."""
        if self.current_index > 0:
            self.current_index -= 1
            self._load_current_photo()
            self.photo_changed.emit(self.current_index)

    def show_next(self):
        """Show next photo."""
        if self.current_index < len(self.photos) - 1:
            self.current_index += 1
            self._load_current_photo()
            self.photo_changed.emit(self.current_index)

    def show_photo_at_index(self, index: int):
        """Show photo at specific index.

        Args:
            index: Index of photo to show
        """
        if 0 <= index < len(self.photos):
            self.current_index = index
            self._load_current_photo()
            self.photo_changed.emit(self.current_index)

    def keyPressEvent(self, event: QKeyEvent):
        """Handle keyboard events.

        Args:
            event: Key event
        """
        key = event.key()

        if key == Qt.Key.Key_Escape:
            self.close()
        elif key == Qt.Key.Key_Left:
            self.show_previous()
        elif key == Qt.Key.Key_Right:
            self.show_next()
        elif key == Qt.Key.Key_Home:
            self.show_photo_at_index(0)
        elif key == Qt.Key.Key_End:
            self.show_photo_at_index(len(self.photos) - 1)
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        """Handle resize event to rescale image.

        Args:
            event: Resize event
        """
        super().resizeEvent(event)
        # Rescale image to fit new window size
        if self._image_loaded and self._original_pixmap:
            QTimer.singleShot(0, self._scale_and_display_image)

    def closeEvent(self, event):
        """Handle close event.

        Args:
            event: Close event
        """
        self.closed.emit()
        super().closeEvent(event)

    def get_current_photo(self):
        """Get currently displayed photo or pair.

        Returns:
            Photo or PhotoPair object
        """
        if 0 <= self.current_index < len(self.photos):
            return self.photos[self.current_index]
        return None

    def is_first_photo(self) -> bool:
        """Check if currently showing first photo.

        Returns:
            True if first photo
        """
        return self.current_index == 0

    def is_last_photo(self) -> bool:
        """Check if currently showing last photo.

        Returns:
            True if last photo
        """
        return self.current_index == len(self.photos) - 1

    def get_photo_count(self) -> int:
        """Get total number of photos.

        Returns:
            Number of photos
        """
        return len(self.photos)

    def __str__(self) -> str:
        """String representation."""
        return f"Lightbox({len(self.photos)} photos, index={self.current_index})"
