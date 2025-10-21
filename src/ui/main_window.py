"""Main application window.

Displays the album grid and handles top-level UI interactions.
"""

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QStatusBar,
    QMessageBox,
    QTabWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from typing import Optional, Callable
from pathlib import Path

from ..models.album import Album
from ..models.app_state import AppState
from .album_grid import AlbumGrid
from .photo_grid import PhotoGrid
from .lightbox import Lightbox
from .library_view import LibraryView
from ..services.library_service import LibraryService
from ..services.photo_processor import PhotoProcessor
from ..utils.thumbnail_cache import ThumbnailCache


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
        self._all_albums: list[Album] = []  # Store all albums before filtering
        self._loading_overlay: Optional[QWidget] = None

        # Load settings
        settings = app_state.load_settings()
        self._hide_empty_albums = settings.get("hide_empty_albums", True)

        # T028: Initialize LibraryService and related services (set defaults first)
        self.library_service = None
        self.thumbnail_cache = None
        self.photo_processor = None
        self._library_loaded = False  # Track if library has been loaded
        self._initialize_library_service()

        # Create UI
        self._create_widgets()
        self._setup_keyboard_shortcuts()

        # T028: Load library in background after UI is ready
        # NOTE: Library loading is deferred - it will be triggered when user clicks Library tab
        # This prevents blocking the main UI during startup
        # self._load_library_async()

    def _initialize_library_service(self):
        """Initialize LibraryService and related services for Library view."""
        import logging
        logger = logging.getLogger(__name__)

        try:
            # Initialize services
            # Create thumbnail cache directory
            cache_dir = self.app_state.photo_dir / "data" / "thumbnails"

            # PhotoProcessor creates its own ThumbnailCache, so just pass cache_dir
            self.photo_processor = PhotoProcessor(cache_dir)

            # Get the ThumbnailCache from PhotoProcessor for use by other components
            self.thumbnail_cache = self.photo_processor.cache

            # Initialize LibraryService
            self.library_service = LibraryService(self.app_state.photo_dir)

            logger.info("LibraryService initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LibraryService: {e}")
            import traceback
            traceback.print_exc()
            self.library_service = None
            self.thumbnail_cache = None
            self.photo_processor = None

    def _load_library_async(self):
        """Load library data in background after UI is ready."""
        if self.library_service:
            from PyQt6.QtCore import QTimer
            import logging
            logger = logging.getLogger(__name__)

            def load():
                try:
                    logger.info("Loading library in background...")
                    self.library_service.load_library()
                    logger.info(f"Library loaded successfully: {self.library_service.get_total_count()} items")

                    # Load library view if it exists
                    if hasattr(self, 'library_view'):
                        logger.info("Initializing library view...")
                        self.library_view.load_library()
                        logger.info("Library view loaded successfully")
                except Exception as e:
                    logger.error(f"Failed to load library: {e}")
                    import traceback
                    traceback.print_exc()

            # Schedule load after UI is shown (1 second delay to let UI fully initialize)
            QTimer.singleShot(1000, load)

    def _on_tab_changed(self, index: int):
        """Handle tab change to load library on-demand when Library tab is selected."""
        import logging
        logger = logging.getLogger(__name__)

        # Check if Library tab was selected (index 1) and library not yet loaded
        if index == 1 and self.library_service and not self._library_loaded:
            logger.info("Library tab selected - loading library on-demand...")
            self._library_loaded = True  # Set flag immediately to prevent double-loading

            # Show loading overlay
            self.show_loading("Scanning photo library...")

            # Load library in background thread
            from PyQt6.QtCore import QThread, pyqtSignal

            class LibraryLoadWorker(QThread):
                """Background worker for loading library."""
                finished = pyqtSignal(int)  # Emits total count when done
                error = pyqtSignal(str)  # Emits error message on failure
                progress = pyqtSignal(int, int, str)  # Emits (current, total, message)

                def __init__(self, library_service, main_window):
                    super().__init__()
                    self.library_service = library_service
                    self.main_window = main_window

                def run(self):
                    try:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.info("Background: Scanning photo directory...")

                        # Load library with progress callback
                        def progress_callback(current, total, message):
                            self.progress.emit(current, total, message)

                        self.library_service.load_library(progress_callback=progress_callback)
                        total = self.library_service.get_total_count()

                        logger.info(f"Background: Library loaded - {total} items")
                        self.finished.emit(total)
                    except Exception as e:
                        logger.error(f"Background: Failed to load library: {e}")
                        import traceback
                        traceback.print_exc()
                        self.error.emit(str(e))

            def on_library_loaded(total: int):
                """Called when library loading completes."""
                try:
                    logger.info(f"Library loaded: {total} items - initializing view...")

                    # Initialize library view on main thread
                    if hasattr(self, 'library_view'):
                        self.library_view.load_library()
                        logger.info("Library view ready")

                    self.hide_loading()
                    self.set_status(f"Library: {total} items")
                except Exception as e:
                    logger.error(f"Failed to initialize library view: {e}")
                    import traceback
                    traceback.print_exc()
                    self.hide_loading()
                    self.set_status("Failed to load library")
                    self._library_loaded = False

            def on_library_progress(current: int, total: int, message: str):
                """Called when library loading makes progress."""
                # Update loading overlay with progress
                progress_pct = int((current / total * 100)) if total > 0 else 0
                self.show_loading(f"{message}\n{current}/{total} ({progress_pct}%)")
                logger.debug(f"Library loading progress: {current}/{total}")

            def on_library_error(error_msg: str):
                """Called when library loading fails."""
                logger.error(f"Library loading failed: {error_msg}")
                self.hide_loading()
                self.set_status("Failed to load library")
                self._library_loaded = False

            # Create and start worker thread
            self._library_worker = LibraryLoadWorker(self.library_service, self)
            self._library_worker.finished.connect(on_library_loaded)
            self._library_worker.error.connect(on_library_error)
            self._library_worker.progress.connect(on_library_progress)
            self._library_worker.start()

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

        # T027: Create main tab widget for Albums and Library
        self.main_tabs = QTabWidget()
        self.main_tabs.setDocumentMode(True)
        # Connect tab change signal to load library on-demand
        self.main_tabs.currentChanged.connect(self._on_tab_changed)
        main_layout.addWidget(self.main_tabs, 1)  # Stretch factor 1

        # Albums tab container
        albums_container = QWidget()
        albums_layout = QVBoxLayout(albums_container)
        albums_layout.setContentsMargins(0, 0, 0, 0)

        # Album grid
        self.album_grid = AlbumGrid(on_album_click=self._handle_album_click)
        albums_layout.addWidget(self.album_grid, 1)

        # Photo grid (hidden initially)
        self.photo_grid = PhotoGrid(
            on_photo_click=lambda photo, idx: None,  # Handle click (future)
            on_photo_double_click=self._handle_photo_double_click,
        )
        self.photo_grid.move_photos_requested.connect(self._handle_move_photos)
        self.photo_grid.hide()
        albums_layout.addWidget(self.photo_grid, 1)

        self.main_tabs.addTab(albums_container, "Albums")

        # T027: Library tab (Phase 3 - User Story 1)
        if self.library_service and self.thumbnail_cache and self.photo_processor:
            import logging
            logger = logging.getLogger(__name__)
            logger.info("Creating Library view...")
            self.library_view = LibraryView(
                self.library_service,
                self.thumbnail_cache,
                self.photo_processor
            )
            self.main_tabs.addTab(self.library_view, "Library")
            logger.info("Library tab added successfully!")
        else:
            # Add placeholder if services failed to initialize
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Library view not available - services failed to initialize:")
            logger.error(f"  library_service: {self.library_service}")
            logger.error(f"  thumbnail_cache: {self.thumbnail_cache}")
            logger.error(f"  photo_processor: {self.photo_processor}")

        # Status bar
        self._create_status_bar()

    def _create_header(self) -> QWidget:
        """Create header with title and controls."""
        from PyQt6.QtWidgets import QPushButton, QCheckBox

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

        # Toggle for hiding empty albums (only visible in album view)
        self.hide_empty_checkbox = QCheckBox("Hide empty albums")
        self.hide_empty_checkbox.setChecked(
            self._hide_empty_albums
        )  # Set from loaded state
        self.hide_empty_checkbox.setToolTip("Hide albums with 0 photos")
        checkbox_font = self.hide_empty_checkbox.font()
        checkbox_font.setPointSize(11)
        self.hide_empty_checkbox.setFont(checkbox_font)
        self.hide_empty_checkbox.stateChanged.connect(self._handle_hide_empty_toggle)
        header_layout.addWidget(self.hide_empty_checkbox)

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

    def _handle_hide_empty_toggle(self, state):
        """Handle hide empty albums checkbox toggle.

        Args:
            state: Qt.CheckState value
        """
        self._hide_empty_albums = state == Qt.CheckState.Checked.value

        # Save the preference
        settings = self.app_state.load_settings()
        settings["hide_empty_albums"] = self._hide_empty_albums
        self.app_state.save_settings(settings)

        # Apply the filter
        self._apply_album_filter()

    def _handle_photo_double_click(self, photo_or_pair, index: int):
        """Handle photo double-click to open lightbox.

        Args:
            photo_or_pair: Photo or PhotoPair object
            index: Index in the photo list
        """
        try:
            # Open lightbox with all photos
            lightbox = Lightbox(
                photos=self._current_photos, current_index=index, parent=self
            )
            lightbox.exec()  # Modal dialog
        except Exception as e:
            self.show_error("Error", f"Could not open photo: {e}")

    def _handle_move_photos(self, photo_paths: list[Path], destination_album: Album):
        """Handle request to move photos to another album.

        Args:
            photo_paths: List of photo file paths to move
            destination_album: Destination album
        """
        try:
            # Import PhotoManager
            from ..services.photo_manager import PhotoManager
            from ..services.filesystem_scanner import FilesystemScanner

            # Create photo manager
            scanner = FilesystemScanner(self.app_state.photo_dir)
            photo_manager = PhotoManager(scanner)

            # Execute move
            result = photo_manager.move_photos(photo_paths, destination_album.path)

            if result["success"]:
                # Show success message
                moved_count = result["moved_count"]
                QMessageBox.information(
                    self,
                    "Photos Moved",
                    f"Successfully moved {moved_count} file(s) to {destination_album.name}",
                )

                # Refresh both source and destination albums
                # Go back to album view and trigger a refresh
                self._handle_back_to_albums()

                # Emit signal to refresh albums (if callback is set)
                if hasattr(self, "on_photos_moved"):
                    self.on_photos_moved(destination_album)

            else:
                # Show error message
                QMessageBox.critical(
                    self, "Move Failed", f"Failed to move photos:\n\n{result['error']}"
                )

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"An error occurred while moving photos:\n\n{str(e)}"
            )

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
        self.hide_empty_checkbox.show()  # Show checkbox in album view
        self.title_label.setText("Photo Albums")
        self._update_status()

    def _show_photo_view(self):
        """Switch to photo view."""
        self._current_view = "photos"
        self.album_grid.hide()
        self.photo_grid.show()
        self.back_button.show()
        self.hide_empty_checkbox.hide()  # Hide checkbox in photo view

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
        self._all_albums = albums
        self._apply_album_filter()

    def _apply_album_filter(self):
        """Apply current filter settings to albums."""
        if self._hide_empty_albums:
            filtered_albums = [
                album for album in self._all_albums if album.photo_count > 0
            ]
        else:
            filtered_albums = self._all_albums

        self.album_grid.set_albums(filtered_albums)
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
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def show_loading(self, message: str = "Loading...", max_value: int = 0):
        """Show loading indicator.

        Args:
            message: Loading message
            max_value: Maximum progress value (0 for indeterminate)
        """
        self.set_status(message)

        # Create loading overlay if it doesn't exist
        if self._loading_overlay is None:
            from PyQt6.QtCore import Qt

            # Create semi-transparent overlay
            self._loading_overlay = QWidget(self.centralWidget())
            self._loading_overlay.setStyleSheet("""
                QWidget {
                    background-color: rgba(0, 0, 0, 0.5);
                }
            """)

            # Create layout for overlay
            overlay_layout = QVBoxLayout(self._loading_overlay)
            overlay_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # Create loading label
            loading_label = QLabel(message)
            loading_label.setStyleSheet("""
                QLabel {
                    background-color: white;
                    color: #333;
                    padding: 20px 40px;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: bold;
                }
            """)
            loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            overlay_layout.addWidget(loading_label)

            # Store reference to label for updates
            self._loading_overlay._label = loading_label
        else:
            # Update message
            self._loading_overlay._label.setText(message)

        # Resize overlay to match central widget
        self._loading_overlay.setGeometry(self.centralWidget().rect())
        self._loading_overlay.raise_()
        self._loading_overlay.show()

        # Process events to show the overlay immediately
        from PyQt6.QtWidgets import QApplication

        QApplication.processEvents()

    def update_loading_progress(self, value: int, message: str = None):
        """Update loading progress.

        Args:
            value: Current progress value
            message: Optional message update
        """
        if message:
            self.set_status(message)
            if self._loading_overlay and hasattr(self._loading_overlay, "_label"):
                self._loading_overlay._label.setText(message)
                from PyQt6.QtWidgets import QApplication

                QApplication.processEvents()

    def hide_loading(self):
        """Hide loading indicator."""
        if self._loading_overlay:
            self._loading_overlay.hide()
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
        self.photo_grid.set_available_albums(self._all_albums)
        self.photo_grid.set_photos(photos)

        self._show_photo_view()

    def clear_photos(self):
        """Clear all photos from display."""
        self.photo_grid.clear()
        self._current_photos.clear()
        self._update_photo_status()

    def show_directory_error(self, directory: Path, error_message: str = None):
        """Show error state when photo directory is unavailable.

        Args:
            directory: Photo directory that is unavailable
            error_message: Optional custom error message
        """
        if error_message is None:
            error_message = (
                f"The photo directory is not accessible:\n\n{directory}\n\n"
                f"Please ensure:\n"
                f"• The directory exists\n"
                f"• You have read permissions\n"
                f"• The drive is mounted (if network/external)\n\n"
                f"The application will now close."
            )

        QMessageBox.critical(self, "Photo Directory Unavailable", error_message)

    def resizeEvent(self, event):
        """Handle window resize to update overlay size.

        Args:
            event: Resize event
        """
        super().resizeEvent(event)
        if self._loading_overlay and self._loading_overlay.isVisible():
            self._loading_overlay.setGeometry(self.centralWidget().rect())

    def __str__(self) -> str:
        """String representation."""
        return f"MainWindow(albums={self.album_grid.get_album_count()})"
