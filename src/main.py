"""Photo Album Organizer - Main Application Entry Point.

Desktop application for organizing photo albums with tile-based UI using PyQt6.
"""

import os
import sys
os.environ['PYTHONUNBUFFERED'] = '1'

import argparse
import time
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import QApplication

from .models.app_state import AppState
from .models.album import Album
from .services.filesystem_scanner import FilesystemScanner
from .services.album_manager import AlbumManager
from .services.photo_processor import PhotoProcessor
from .utils.thumbnail_cache import ThumbnailCache
from .ui.main_window import MainWindow


class PhotoOrganizerApp:
    """Main application class.

    Orchestrates services and UI components.
    """

    def __init__(self, photo_dir: Path, state_file: Optional[Path] = None):
        """Initialize application.

        Args:
            photo_dir: Root directory containing photo albums
            state_file: Optional path to state file (default: data/app_state.json)
        """
        self.photo_dir = Path(photo_dir)

        # Validate photo directory
        if not self.photo_dir.exists():
            raise ValueError(f"Photo directory does not exist: {self.photo_dir}")
        if not self.photo_dir.is_dir():
            raise ValueError(f"Photo path is not a directory: {self.photo_dir}")

        # Initialize app state
        if state_file is None:
            state_file = Path.cwd() / "data" / "app_state.json"

        self.app_state = AppState(
            photo_dir=self.photo_dir,
            state_file=state_file
        )

        # Initialize services
        self.scanner = FilesystemScanner(self.photo_dir)

        # Initialize thumbnail cache and photo processor
        cache_dir = Path.cwd() / "data" / "thumbnails"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.photo_processor = PhotoProcessor(cache_dir)

        self.album_manager = AlbumManager(
            app_state=self.app_state,
            scanner=self.scanner,
            photo_processor=self.photo_processor,
            on_albums_changed=self._handle_albums_changed
        )

        # UI
        self.window: Optional[MainWindow] = None

        # State
        self._startup_time = time.time()

    def run(self, qt_app: QApplication):
        """Start the application.

        Must complete startup in < 2 seconds per constitution.

        Args:
            qt_app: QApplication instance
        """
        print(f"Starting Photo Album Organizer...")
        print(f"Photo directory: {self.photo_dir}")

        # Create main window
        self.window = MainWindow(
            app_state=self.app_state,
            on_album_open=self._handle_album_open
        )

        # Connect album grid signals for drag-drop reordering
        self.window.album_grid.albums_reordered.connect(self._handle_albums_reordered)
        self.window.album_grid.revert_to_chronological_requested.connect(
            self._handle_revert_to_chronological
        )

        # Load albums
        print("Loading albums...")
        self.window.show_loading("Loading albums...")

        albums = self.album_manager.load_albums()

        print(f"Loaded {len(albums)} albums")

        # Display albums
        self.window.show_albums(albums)
        self.window.hide_loading()

        # Log startup time
        startup_time = time.time() - self._startup_time
        print(f"Startup completed in {startup_time:.2f}s")

        if startup_time > 2.0:
            print(f"WARNING: Startup time exceeded 2s target ({startup_time:.2f}s)")

        # Center and show window
        self.window.center_window()
        self.window.show()

        # Run Qt event loop
        print("Application ready")
        sys.exit(qt_app.exec())

    def _shutdown(self):
        """Cleanup on application shutdown."""
        print("Shutting down...")
        print("Goodbye!")

    # ==================== Event Handlers ====================

    def _handle_album_open(self, album: Album):
        """Handle album being opened.

        Args:
            album: Album to open
        """
        print(f"Opening album: {album.name}")

        if not self.window:
            return

        try:
            # Show loading indicator
            self.window.show_loading(f"Loading photos from {album.name}...")

            # Load photos with RAW-JPEG deduplication
            photo_pairs = self.album_manager.load_photos_with_deduplication(album)

            print(f"Loaded {len(photo_pairs)} photos (after deduplication)")

            # Generate thumbnails for photos
            if len(photo_pairs) > 0:
                print("Generating thumbnails...")
                # Get all photos from pairs for thumbnail generation
                all_photos = self.album_manager.load_photos(album)
                self.album_manager.generate_thumbnails_for_album(album, all_photos)

            # Display photos in grid
            self.window.show_photos(album, photo_pairs)

            print(f"Album opened successfully: {album.name}")

        except Exception as e:
            print(f"Error opening album: {e}")
            import traceback
            traceback.print_exc()

            if self.window:
                self.window.hide_loading()
                self.window.show_error(
                    "Error Opening Album",
                    f"Could not open album '{album.name}':\n\n{str(e)}"
                )

    def _handle_albums_changed(self, albums: list[Album]):
        """Handle albums list being changed.

        Args:
            albums: Updated albums list
        """
        if self.window:
            import traceback
            print(f"Albums changed: {len(albums)} albums")
            print("Call stack:")
            for line in traceback.format_stack()[:-1]:
                print(line.strip())
            self.window.show_albums(albums)

    def _handle_albums_reordered(self, albums: list[Album]):
        """Handle albums being reordered via drag-drop.

        Args:
            albums: Albums in new order
        """
        print(f"DEBUG: _handle_albums_reordered called with {len(albums)} albums")
        for i, album in enumerate(albums):
            print(f"  {i}: {album.name}")

        # Update album manager with new custom order
        self.album_manager.set_custom_order(albums)
        print(f"DEBUG: Custom order saved to album manager")

        # Status update
        if self.window:
            self.window.set_status("Album order saved")

    def _handle_revert_to_chronological(self):
        """Handle request to revert to chronological ordering."""
        print("Reverting to chronological order")

        # Revert to chronological order in album manager
        self.album_manager.revert_to_chronological_order()

        # The albums_changed callback will update the UI
        if self.window:
            self.window.set_status("Reverted to chronological order")



def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Photo Album Organizer - Organize and browse photo albums"
    )

    parser.add_argument(
        "--photo-dir",
        type=Path,
        default=Path.home() / "Pictures",
        help="Root directory containing photo albums (default: ~/Pictures)"
    )

    parser.add_argument(
        "--state-file",
        type=Path,
        default=None,
        help="Path to state file for persistent data (default: data/app_state.json)"
    )

    parser.add_argument(
        "--version",
        action="version",
        version="Photo Album Organizer v0.1.0"
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    try:
        # Parse arguments
        args = parse_arguments()

        # Create QApplication
        qt_app = QApplication(sys.argv)
        qt_app.setApplicationName("Photo Album Organizer")
        qt_app.setOrganizationName("PhotoOrganizer")

        # Create and run application
        app = PhotoOrganizerApp(
            photo_dir=args.photo_dir,
            state_file=args.state_file
        )

        app.run(qt_app)

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(0)

    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
