"""Main application window.

Displays the album grid and handles top-level UI interactions.
"""

from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStatusBar, QMessageBox
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QKeySequence, QShortcut, QScreen
from typing import Optional, Callable
from pathlib import Path

from ..models.album import Album
from ..models.photo import Photo, PhotoPair
from ..models.app_state import AppState
from .album_grid import AlbumGrid
from .photo_grid import PhotoGrid
from .lightbox import Lightbox


class MainWindow(QMainWindow):
    """Main application window.

    Features:
    - Album grid display
    - Application title and status
    - Window management (resize, close)
    """

    def __init__(
        self,
        app_state: AppState,
        on_album_open: Optional[Callable[[Album], None]] = None,
    ):
        """Initialize main window.

        Args:
            app_state: Application state
            on_album_open: Callback when album is opened
        """
        super().__init__()

        self.app_state = app_state
        self.on_album_open = on_album_open

        # Window configuration
        self.setWindowTitle("Photo Album Organizer")
        self.resize(1200, 800)
        self.setMinimumSize(800, 600)

        # State
        self._current_view = "albums"  # "albums" or "photos"
        self._current_album: Optional[Album] = None
        self._current_photos: list = []  # List[Photo | PhotoPair]
        self._is_fullscreen = False

        # Create UI
        self._create_widgets()
        self._setup_keyboard_shortcuts()

    def _create_widgets(self):
        """Create main window widgets."""
        # Central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Header frame
        header_widget = self._create_header()
        main_layout.addWidget(header_widget)

        # Album grid
        self.album_grid = AlbumGrid(
            on_album_click=self._handle_album_click
        )
        main_layout.addWidget(self.album_grid, 1)  # Stretch factor 1

        # Photo grid (hidden initially)
        self.photo_grid = PhotoGrid(
            on_photo_click=lambda photo, idx: None,  # Handle click (future)
            on_photo_double_click=self._handle_photo_double_click
        )
        self.photo_grid.hide()
        main_layout.addWidget(self.photo_grid, 1)  # Stretch factor 1

        # Status bar
        self._create_status_bar()

    def _create_header(self) -> QWidget:
        """Create header with title and controls."""
        from PyQt6.QtWidgets import QPushButton

        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 10, 10, 10)

        # Back button (hidden initially)
        self.back_button = QPushButton("← Back to Albums")
        self.back_button.setFixedHeight(35)
        self.back_button.setStyleSheet("""
            QPushButton {
                background-color: #4a90e2;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
            QPushButton:pressed {
                background-color: #2868a8;
            }
        """)
        self.back_button.clicked.connect(self._handle_back_to_albums)
        self.back_button.hide()
        header_layout.addWidget(self.back_button)

        # Title
        self.title_label = QLabel("Photo Albums")
        title_font = self.title_label.font()
        title_font.setPointSize(24)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        header_layout.addWidget(self.title_label)

        # Photo directory info
        dir_text = f"📁 {self.app_state.photo_dir}"
        dir_label = QLabel(dir_text)
        dir_font = dir_label.font()
        dir_font.setPointSize(12)
        dir_label.setFont(dir_font)
        dir_label.setStyleSheet("color: gray;")
        header_layout.addWidget(dir_label)

        header_layout.addStretch()  # Push everything to the left

        return header_widget

    def _create_status_bar(self):
        """Create status bar at bottom of window."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Quit: Ctrl+Q
        quit_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        quit_shortcut.activated.connect(self.close)

        # Refresh: F5
        refresh_shortcut = QShortcut(QKeySequence("F5"), self)
        refresh_shortcut.activated.connect(self._handle_refresh)

        # Fullscreen: F11
        fullscreen_shortcut = QShortcut(QKeySequence("F11"), self)
        fullscreen_shortcut.activated.connect(self._toggle_fullscreen)

        # Escape: Exit fullscreen
        escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        escape_shortcut.activated.connect(self._handle_escape)

    def _handle_album_click(self, album: Album):
        """Handle album click event.

        Args:
            album: Album that was clicked
        """
        if self.on_album_open:
            self.on_album_open(album)

    def _handle_refresh(self):
        """Handle refresh request."""
        self.set_status("Refreshing albums...")
        # Refresh will be triggered by the main app
        # Reset status after a short delay
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, lambda: self.set_status("Ready"))

    def _handle_escape(self):
        """Handle Escape key press."""
        if self._is_fullscreen:
            self._toggle_fullscreen()
        elif self._current_view == "photos":
            # Go back to albums if in photo view
            self._handle_back_to_albums()

    def _handle_back_to_albums(self):
        """Handle back button click to return to album view."""
        self._show_album_view()
        self._current_album = None
        self._current_photos.clear()

    def _handle_photo_double_click(self, photo_or_pair, index: int):
        """Handle photo double-click to open lightbox.

        Args:
            photo_or_pair: Photo or PhotoPair object
            index: Index in the photo list
        """
        try:
            # Open lightbox with all photos
            lightbox = Lightbox(
                photos=self._current_photos,
                current_index=index,
                parent=self
            )
            lightbox.exec()  # Modal dialog
        except Exception as e:
            self.show_error("Error", f"Could not open photo: {e}")

    def _toggle_fullscreen(self):
        """Toggle fullscreen mode."""
        if self._is_fullscreen:
            self.showNormal()
            self._is_fullscreen = False
        else:
            self.showFullScreen()
            self._is_fullscreen = True

    def _show_album_view(self):
        """Switch to album view."""
        self._current_view = "albums"
        self.photo_grid.hide()
        self.album_grid.show()
        self.back_button.hide()
        self.title_label.setText("Photo Albums")
        self._update_status()

    def _show_photo_view(self):
        """Switch to photo view."""
        self._current_view = "photos"
        self.album_grid.hide()
        self.photo_grid.show()
        self.back_button.show()

        if self._current_album:
            self.title_label.setText(f"{self._current_album.name}")

        self._update_photo_status()

    def _update_photo_status(self):
        """Update status bar for photo view."""
        photo_count = self.photo_grid.get_photo_count()
        if photo_count == 0:
            self.set_status("No photos in this album")
        elif photo_count == 1:
            self.set_status("1 photo")
        else:
            self.set_status(f"{photo_count} photos")

    # ==================== Public API ====================

    def show_albums(self, albums: list[Album]):
        """Display albums in the grid.

        Args:
            albums: List of albums to display
        """
        self.album_grid.set_albums(albums)
        self._update_status()

    def clear_albums(self):
        """Clear all albums from display."""
        self.album_grid.clear()
        self._update_status()

    def refresh_album(self, album: Album):
        """Refresh a specific album display.

        Args:
            album: Album to refresh
        """
        self.album_grid.refresh_album(album)

    def refresh_display(self):
        """Refresh the entire display."""
        self.album_grid.refresh()
        self._update_status()

    def get_displayed_albums(self) -> list[Album]:
        """Get currently displayed albums.

        Returns:
            List of albums
        """
        return self.album_grid.get_albums()

    def find_album_by_path(self, path: Path) -> Optional[Album]:
        """Find displayed album by path.

        Args:
            path: Path to album directory

        Returns:
            Album if found, None otherwise
        """
        return self.album_grid.find_album_by_path(path)

    def scroll_to_album(self, album: Album):
        """Scroll to show a specific album.

        Args:
            album: Album to scroll to
        """
        self.album_grid.scroll_to_album(album)

    def scroll_to_top(self):
        """Scroll to top of album grid."""
        self.album_grid.scroll_to_top()

    def set_status(self, message: str):
        """Set status bar message.

        Args:
            message: Status message to display
        """
        self.status_bar.showMessage(message)

    def _update_status(self):
        """Update status bar with current stats."""
        album_count = self.album_grid.get_album_count()
        if album_count == 0:
            self.set_status("No albums found")
        elif album_count == 1:
            self.set_status("1 album")
        else:
            self.set_status(f"{album_count} albums")

    def show_error(self, title: str, message: str):
        """Show error dialog.

        Args:
            title: Error title
            message: Error message
        """
        QMessageBox.critical(self, title, message)

    def show_info(self, title: str, message: str):
        """Show info dialog.

        Args:
            title: Info title
            message: Info message
        """
        QMessageBox.information(self, title, message)

    def ask_yes_no(self, title: str, message: str) -> bool:
        """Show yes/no confirmation dialog.

        Args:
            title: Dialog title
            message: Dialog message

        Returns:
            True if yes, False if no
        """
        reply = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes

    def show_loading(self, message: str = "Loading..."):
        """Show loading indicator.

        Args:
            message: Loading message
        """
        self.set_status(message)
        # TODO: Add visual loading indicator

    def hide_loading(self):
        """Hide loading indicator."""
        self._update_status()

    def set_window_title(self, title: str):
        """Set window title.

        Args:
            title: New window title
        """
        self.setWindowTitle(title)

    def center_window(self):
        """Center window on screen."""
        # Get the screen geometry
        screen = self.screen()
        if screen:
            screen_geometry = screen.availableGeometry()
            window_geometry = self.frameGeometry()
            center_point = screen_geometry.center()
            window_geometry.moveCenter(center_point)
            self.move(window_geometry.topLeft())

    def run(self):
        """Start the main event loop."""
        # In PyQt6, the event loop is managed by QApplication
        # This method is kept for compatibility but does nothing
        pass

    def show_photos(self, album: Album, photos: list):
        """Display photos for an album.

        Args:
            album: Album whose photos to display
            photos: List of Photo or PhotoPair objects
        """
        self._current_album = album
        self._current_photos = photos

        self.photo_grid.set_album(album)
        self.photo_grid.set_photos(photos)

        self._show_photo_view()

    def clear_photos(self):
        """Clear all photos from display."""
        self.photo_grid.clear()
        self._current_photos.clear()
        self._update_photo_status()

    def __str__(self) -> str:
        """String representation."""
        return f"MainWindow(albums={self.album_grid.get_album_count()})"
