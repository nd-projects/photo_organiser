"""Photo Album Organizer - Main Application Entry Point.

Desktop application for organizing photo albums with tile-based UI using PyQt6.
"""

import os
import sys

os.environ["PYTHONUNBUFFERED"] = "1"

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
from .utils.logging_config import setup_logging, get_logger
from .utils.config_loader import ConfigLoader, AppConfig
from .ui.main_window import MainWindow

# Initialize logger
logger = get_logger(__name__)


class PhotoOrganizerApp:
    """Main application class.

    Orchestrates services and UI components.
    """

    def __init__(
        self,
        photo_dir: Path,
        state_file: Optional[Path] = None,
        cache_dir: Optional[Path] = None,
    ):
        """Initialize application.

        Args:
            photo_dir: Root directory containing photo albums
            state_file: Optional path to state file (default: data/app_state.json)
            cache_dir: Optional path to thumbnail cache directory (default: data/thumbnails)
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

        self.app_state = AppState(photo_dir=self.photo_dir, state_file=state_file)

        # Initialize services
        self.scanner = FilesystemScanner(self.photo_dir)

        # Initialize thumbnail cache and photo processor
        if cache_dir is None:
            cache_dir = Path.cwd() / "data" / "thumbnails"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.photo_processor = PhotoProcessor(cache_dir)

        self.album_manager = AlbumManager(
            app_state=self.app_state,
            scanner=self.scanner,
            photo_processor=self.photo_processor,
            on_albums_changed=self._handle_albums_changed,
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
        logger.info("Starting Photo Album Organizer...")
        logger.info(f"Photo directory: {self.photo_dir}")

        # Create main window
        self.window = MainWindow(
            app_state=self.app_state, on_album_open=self._handle_album_open
        )

        # Connect album grid signals for drag-drop reordering
        self.window.album_grid.albums_reordered.connect(self._handle_albums_reordered)
        self.window.album_grid.revert_to_chronological_requested.connect(
            self._handle_revert_to_chronological
        )

        # Connect album creation and rename signals
        self.window.album_grid.create_album_requested.connect(self._handle_create_album)
        self.window.album_grid.rename_album_requested.connect(self._handle_rename_album)

        # Load albums
        logger.info("Loading albums...")
        self.window.show_loading("Loading albums...")

        albums = self.album_manager.load_albums()

        logger.info(f"Loaded {len(albums)} albums")

        # Display albums
        self.window.show_albums(albums)
        self.window.hide_loading()

        # Log startup time
        startup_time = time.time() - self._startup_time
        logger.info(f"Startup completed in {startup_time:.2f}s")

        if startup_time > 2.0:
            logger.warning(f"Startup time exceeded 2s target ({startup_time:.2f}s)")

        # Center and show window
        self.window.center_window()
        self.window.show()

        # Run Qt event loop
        logger.info("Application ready")
        sys.exit(qt_app.exec())

    def _shutdown(self):
        """Cleanup on application shutdown."""
        logger.info("Shutting down...")
        logger.info("Goodbye!")

    # ==================== Event Handlers ====================

    def _handle_album_open(self, album: Album):
        """Handle album being opened.

        Args:
            album: Album to open
        """
        logger.info(f"Opening album: {album.name}")

        if not self.window:
            return

        try:
            # Show loading indicator
            self.window.show_loading(f"Loading photos from {album.name}...")

            # Load photos with RAW-JPEG deduplication
            photo_pairs = self.album_manager.load_photos_with_deduplication(album)

            logger.info(f"Loaded {len(photo_pairs)} photos (after deduplication)")

            # Generate thumbnails for photos
            if len(photo_pairs) > 0:
                logger.info("Generating thumbnails...")
                # Get all photos from pairs for thumbnail generation
                all_photos = self.album_manager.load_photos(album)
                self.album_manager.generate_thumbnails_for_album(album, all_photos)

            # Display photos in grid
            self.window.show_photos(album, photo_pairs)

            # Hide loading indicator
            self.window.hide_loading()

            logger.info(f"Album opened successfully: {album.name}")

        except Exception as e:
            logger.error(f"Error opening album: {e}")
            import traceback

            traceback.print_exc()

            if self.window:
                self.window.hide_loading()
                self.window.show_error(
                    "Error Opening Album",
                    f"Could not open album '{album.name}':\n\n{str(e)}",
                )

    def _handle_albums_changed(self, albums: list[Album]):
        """Handle albums list being changed.

        Args:
            albums: Updated albums list
        """
        if self.window:
            self.window.show_albums(albums)

    def _handle_albums_reordered(self, albums: list[Album]):
        """Handle albums being reordered via drag-drop.

        Args:
            albums: Albums in new order
        """
        logger.debug(f" _handle_albums_reordered called with {len(albums)} albums")
        for i, album in enumerate(albums):
            logger.debug(f"  {i}: {album.name}")

        # Update album manager with new custom order
        self.album_manager.set_custom_order(albums)
        logger.debug(" Custom order saved to album manager")

        # Status update
        if self.window:
            self.window.set_status("Album order saved")

    def _handle_revert_to_chronological(self):
        """Handle request to revert to chronological ordering."""
        logger.info("Reverting to chronological order")

        # Revert to chronological order in album manager
        self.album_manager.revert_to_chronological_order()

        # The albums_changed callback will update the UI
        if self.window:
            self.window.set_status("Reverted to chronological order")

    def _handle_create_album(self, album_name: str):
        """Handle request to create a new album.

        Args:
            album_name: Name for the new album
        """
        from .utils.file_validator import FileValidator

        logger.info(f"Creating album: {album_name}")

        if not self.window:
            return

        try:
            # Validate album name and check availability
            is_valid, error_msg = FileValidator.validate_and_check_availability(
                self.photo_dir, album_name
            )

            if not is_valid:
                # Show error message
                self.window.album_grid.show_error("Invalid Album Name", error_msg)
                return

            # Create album
            album = self.album_manager.create_album(album_name)

            if album:
                logger.info(f"Album created successfully: {album_name}")
                self.window.set_status(f"Created album: {album_name}")
                # Refresh the album list
                albums = self.album_manager.get_albums()
                self.window.show_albums(albums)
            else:
                self.window.album_grid.show_error(
                    "Error Creating Album", f"Could not create album '{album_name}'"
                )

        except ValueError as e:
            # Handle validation errors from album_manager
            self.window.album_grid.show_error("Invalid Album Name", str(e))
        except Exception as e:
            logger.error(f"Error creating album: {e}")
            import traceback

            traceback.print_exc()
            self.window.album_grid.show_error(
                "Error Creating Album", f"An unexpected error occurred:\n\n{str(e)}"
            )

    def _handle_rename_album(self, album: Album, new_name: str):
        """Handle request to rename an album.

        Args:
            album: Album to rename
            new_name: New name for the album
        """
        from .utils.file_validator import FileValidator

        logger.info(f"Renaming album '{album.name}' to '{new_name}'")

        if not self.window:
            return

        try:
            # Validate new name
            is_valid, error_msg = FileValidator.validate_album_name(new_name)
            if not is_valid:
                self.window.album_grid.show_error("Invalid Album Name", error_msg)
                return

            # Check if new name is available (if different from current name)
            if new_name != album.name:
                if not FileValidator.is_album_name_available(self.photo_dir, new_name):
                    self.window.album_grid.show_error(
                        "Album Already Exists",
                        f"An album with the name '{new_name}' already exists.",
                    )
                    return

            # Rename album
            success = self.album_manager.rename_album(album, new_name)

            if success:
                logger.info(
                    f"Album renamed successfully: '{album.name}' -> '{new_name}'"
                )
                self.window.set_status(f"Renamed album to: {new_name}")
                # The albums_changed callback will update the UI
            else:
                self.window.album_grid.show_error(
                    "Error Renaming Album", f"Could not rename album to '{new_name}'"
                )

        except ValueError as e:
            # Handle validation errors from album_manager
            self.window.album_grid.show_error("Invalid Album Name", str(e))
        except Exception as e:
            logger.error(f"Error renaming album: {e}")
            import traceback

            traceback.print_exc()
            self.window.album_grid.show_error(
                "Error Renaming Album", f"An unexpected error occurred:\n\n{str(e)}"
            )


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Photo Album Organizer - Organize and browse photo albums",
        epilog="Configuration can be provided via a TOML file (see --config) or CLI arguments. "
        "CLI arguments take precedence over config file settings.",
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to configuration file (TOML format). If not specified, searches default locations: "
        "./config.toml, ~/.config/photo-organizer/config.toml, /etc/photo-organizer/config.toml",
    )

    parser.add_argument(
        "--photo-dir",
        type=Path,
        default=None,
        help="Root directory containing photo albums (overrides config file)",
    )

    parser.add_argument(
        "--state-file",
        type=Path,
        default=None,
        help="Path to state file for persistent data (default: data/app_state.json)",
    )

    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Directory for thumbnail cache (default: data/thumbnails)",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: INFO)",
    )

    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Path to log file (default: no file logging)",
    )

    parser.add_argument(
        "--create-config",
        type=Path,
        metavar="PATH",
        help="Create an example configuration file at the specified path and exit",
    )

    parser.add_argument(
        "--version", action="version", version="Photo Album Organizer v0.8.0"
    )

    return parser.parse_args()


def merge_config_and_args(
    config: Optional[AppConfig], args: argparse.Namespace
) -> AppConfig:
    """Merge configuration file and command-line arguments.

    CLI arguments take precedence over config file settings.

    Args:
        config: Configuration loaded from file (or None)
        args: Command-line arguments

    Returns:
        Merged configuration

    Raises:
        ValueError: If required configuration is missing
    """
    # Start with config file values or defaults
    if config:
        photo_dir = config.photo_dir
        state_file = config.state_file
        cache_dir = config.cache_dir
        log_level = config.log_level
        log_file = config.log_file
    else:
        # Default values when no config file
        photo_dir = Path.home() / "Pictures"
        state_file = None
        cache_dir = None
        log_level = "INFO"
        log_file = None

    # CLI arguments override config file
    if args.photo_dir is not None:
        photo_dir = args.photo_dir
    if args.state_file is not None:
        state_file = args.state_file
    if args.cache_dir is not None:
        cache_dir = args.cache_dir
    if args.log_level is not None:
        log_level = args.log_level
    if args.log_file is not None:
        log_file = args.log_file

    # Create merged config
    merged = AppConfig(
        photo_dir=photo_dir,
        state_file=state_file,
        cache_dir=cache_dir,
        log_level=log_level,
        log_file=log_file,
    )

    # Validate
    is_valid, error_msg = merged.validate()
    if not is_valid:
        raise ValueError(error_msg)

    return merged


def main():
    """Main entry point."""
    qt_app = None

    try:
        # Parse arguments
        args = parse_arguments()

        # Handle --create-config
        if args.create_config:
            ConfigLoader.create_example_config(args.create_config)
            print(f"Created example configuration file: {args.create_config}")
            sys.exit(0)

        # Load configuration file (if exists)
        try:
            config = ConfigLoader.load_config(args.config)
            if config:
                print("Loaded configuration from file")
        except ValueError as e:
            print(f"Error loading config file: {e}", file=sys.stderr)
            sys.exit(1)

        # Merge config file and CLI arguments
        try:
            final_config = merge_config_and_args(config, args)
        except ValueError as e:
            print(f"Configuration error: {e}", file=sys.stderr)
            sys.exit(1)

        # Setup logging
        setup_logging(
            log_level=final_config.log_level,
            log_file=final_config.log_file,
            console=True,
        )

        logger.info("Photo Album Organizer v0.8.0")
        logger.info(f"Photo directory: {final_config.photo_dir}")
        if config:
            logger.info(
                "Configuration loaded from file (CLI arguments take precedence)"
            )

        # Create QApplication
        qt_app = QApplication(sys.argv)
        qt_app.setApplicationName("Photo Album Organizer")
        qt_app.setOrganizationName("PhotoOrganizer")

        # Validate photo directory before creating app
        if not final_config.photo_dir.exists() or not final_config.photo_dir.is_dir():
            from PyQt6.QtWidgets import QMessageBox

            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("Photo Directory Unavailable")
            msg.setText(
                f"The photo directory is not accessible:\n\n{final_config.photo_dir}"
            )
            msg.setInformativeText(
                "Please ensure:\n"
                "• The directory exists\n"
                "• You have read permissions\n"
                "• The drive is mounted (if network/external)"
            )
            msg.exec()
            sys.exit(1)

        # Create and run application
        app = PhotoOrganizerApp(
            photo_dir=final_config.photo_dir,
            state_file=final_config.state_file,
            cache_dir=final_config.cache_dir,
        )

        app.run(qt_app)

    except ValueError as e:
        # Directory validation error
        logger.error(f"Photo directory validation error: {e}")
        if qt_app:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(None, "Error", str(e))
        sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)

    except Exception as e:
        # Unexpected error
        logger.exception(f"Unexpected error: {e}")
        if qt_app:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(
                None,
                "Unexpected Error",
                f"An unexpected error occurred:\n\n{str(e)}\n\nSee logs for details.",
            )
        sys.exit(1)


if __name__ == "__main__":
    main()
