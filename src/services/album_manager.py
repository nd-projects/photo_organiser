"""Album manager service for loading and managing photo albums.

Handles:
- Loading albums from filesystem
- Custom album ordering with JSON persistence
- Default chronological sorting
- Album operations (CRUD)
"""

import json
from pathlib import Path
from typing import List, Optional, Callable
from datetime import datetime, date

from ..models.album import Album
from ..models.photo import Photo, PhotoPair
from ..models.app_state import AppState
from ..utils.file_validator import FileValidator
from .filesystem_scanner import FilesystemScanner
from .photo_processor import PhotoProcessor


class AlbumManager:
    """Service for managing photo albums.

    Responsibilities:
    - Load albums from filesystem
    - Persist and restore custom ordering
    - Apply sorting (chronological or custom)
    - Notify observers of changes
    """

    def __init__(
        self,
        app_state: AppState,
        scanner: FilesystemScanner,
        photo_processor: Optional[PhotoProcessor] = None,
        on_albums_changed: Optional[Callable[[List[Album]], None]] = None
    ):
        """Initialize album manager.

        Args:
            app_state: Application state object
            scanner: Filesystem scanner service
            photo_processor: Photo processor for thumbnail generation
            on_albums_changed: Optional callback when albums change
        """
        self.app_state = app_state
        self.scanner = scanner
        self.photo_processor = photo_processor
        self.on_albums_changed = on_albums_changed

        # Current albums
        self._albums: List[Album] = []

        # Custom ordering (album_path -> sort_index)
        self._custom_order: dict[str, int] = {}

        # Cache of loaded photos per album (album_path -> list of photos)
        self._photo_cache: dict[str, List[Photo]] = {}

        # Load custom ordering from state file
        self._load_custom_ordering()

    def load_albums(self) -> List[Album]:
        """Load all albums from filesystem.

        Returns:
            List of albums, sorted according to custom ordering or chronologically
        """
        # Scan filesystem for albums
        self._albums = self.scanner.scan_albums()

        # Apply ordering
        if self._has_custom_order():
            self._apply_custom_order()
        else:
            self._apply_default_chronological_sort()

        # Generate album thumbnails
        self._generate_album_thumbnails()

        # Notify observers
        self._notify_albums_changed()

        return self._albums

    def get_albums(self) -> List[Album]:
        """Get current list of albums.

        Returns:
            List of albums
        """
        return self._albums.copy()

    def get_album_by_path(self, path: Path) -> Optional[Album]:
        """Get album by its path.

        Args:
            path: Path to album directory

        Returns:
            Album if found, None otherwise
        """
        for album in self._albums:
            if album.path == path:
                return album
        return None

    def refresh_albums(self) -> List[Album]:
        """Refresh albums from filesystem.

        Detects new albums, removed albums, and updates existing ones.

        Returns:
            Updated list of albums
        """
        return self.load_albums()

    def refresh_album(self, album: Album) -> Album:
        """Refresh a specific album's metadata.

        Args:
            album: Album to refresh

        Returns:
            Updated album object
        """
        return self.scanner.refresh_album(album)

    # ==================== Ordering Methods ====================

    def _has_custom_order(self) -> bool:
        """Check if custom ordering exists.

        Returns:
            True if custom ordering is defined
        """
        return len(self._custom_order) > 0

    def _apply_default_chronological_sort(self):
        """Apply default chronological sorting (newest to oldest).

        Albums without dates are placed at the end.
        """
        # Sort by date, newest first
        # Albums without dates go to the end
        self._albums.sort(
            key=lambda album: album.date if album.date else date.min,
            reverse=True
        )

    def _apply_custom_order(self):
        """Apply custom ordering from saved state.

        Albums not in custom order are placed at the end chronologically.
        """
        # Separate albums into ordered and unordered
        ordered = []
        unordered = []

        for album in self._albums:
            album_path = str(album.path)
            if album_path in self._custom_order:
                ordered.append((self._custom_order[album_path], album))
            else:
                unordered.append(album)

        # Sort ordered albums by their sort index
        ordered.sort(key=lambda x: x[0])
        ordered_albums = [album for _, album in ordered]

        # Sort unordered albums chronologically
        unordered.sort(
            key=lambda album: album.date if album.date else date.min,
            reverse=True
        )

        # Combine: custom ordered first, then chronological
        self._albums = ordered_albums + unordered

    def set_custom_order(self, ordered_albums: List[Album]):
        """Set custom album ordering.

        Args:
            ordered_albums: List of albums in desired order
        """
        # Build custom order mapping
        self._custom_order.clear()
        for idx, album in enumerate(ordered_albums):
            self._custom_order[str(album.path)] = idx

        # Update albums list
        self._albums = ordered_albums.copy()

        # Save to state file
        self._save_custom_ordering()

        # Notify observers
        self._notify_albums_changed()

    def revert_to_chronological_order(self):
        """Revert to default chronological ordering.

        Clears custom ordering.
        """
        # Clear custom order
        self._custom_order.clear()

        # Apply chronological sort
        self._apply_default_chronological_sort()

        # Save state (empty custom order)
        self._save_custom_ordering()

        # Notify observers
        self._notify_albums_changed()

    def move_album(self, album: Album, new_index: int):
        """Move an album to a new position.

        Args:
            album: Album to move
            new_index: New index position (0-based)
        """
        try:
            # Find current index
            current_index = self._albums.index(album)

            # Remove from current position
            self._albums.pop(current_index)

            # Insert at new position
            self._albums.insert(new_index, album)

            # Update custom order
            self._update_custom_order_from_list()

            # Save state
            self._save_custom_ordering()

            # Notify observers
            self._notify_albums_changed()

        except ValueError:
            # Album not in list
            pass

    def _update_custom_order_from_list(self):
        """Update custom order mapping from current album list."""
        self._custom_order.clear()
        for idx, album in enumerate(self._albums):
            self._custom_order[str(album.path)] = idx

    # ==================== Persistence Methods ====================

    def _load_custom_ordering(self):
        """Load custom album ordering from JSON state file."""
        state_file = self.app_state.state_file

        if not state_file.exists():
            return

        try:
            with open(state_file, 'r') as f:
                data = json.load(f)

                # Extract album_order array
                album_order = data.get('album_order', [])

                # Build custom order mapping
                self._custom_order.clear()
                for entry in album_order:
                    album_path = entry.get('album_path')
                    sort_index = entry.get('sort_index')

                    if album_path and sort_index is not None:
                        self._custom_order[album_path] = sort_index

        except (json.JSONDecodeError, KeyError, IOError) as e:
            print(f"Warning: Could not load custom ordering: {e}")
            self._custom_order.clear()

    def _save_custom_ordering(self):
        """Save custom album ordering to JSON state file."""
        state_file = self.app_state.state_file

        # Ensure parent directory exists
        state_file.parent.mkdir(parents=True, exist_ok=True)

        # Build album_order array
        album_order = []
        for album_path, sort_index in sorted(self._custom_order.items(), key=lambda x: x[1]):
            album_order.append({
                'album_path': album_path,
                'sort_index': sort_index,
                'metadata': {},
                'updated_at': datetime.now().isoformat()
            })

        # Create state data
        state_data = {
            'version': '1.0',
            'album_order': album_order
        }

        try:
            with open(state_file, 'w') as f:
                json.dump(state_data, f, indent=2)
        except IOError as e:
            print(f"Error: Could not save custom ordering: {e}")

    # ==================== Album Operations ====================

    def create_album(self, album_name: str) -> Optional[Album]:
        """Create a new album directory.

        Args:
            album_name: Name for the new album

        Returns:
            Created Album object, or None if creation failed
        """
        # Validate album name
        if not self._is_valid_album_name(album_name):
            raise ValueError(f"Invalid album name: {album_name}")

        # Create album directory
        album_path = self.app_state.photo_dir / album_name

        if album_path.exists():
            raise ValueError(f"Album already exists: {album_name}")

        try:
            album_path.mkdir(parents=False)

            # Create Album object
            album = Album(path=album_path)

            # Add to albums list
            self._albums.append(album)

            # Save state
            self._notify_albums_changed()

            return album

        except OSError as e:
            print(f"Error: Could not create album directory: {e}")
            return None

    def rename_album(self, album: Album, new_name: str) -> bool:
        """Rename an album directory.

        Args:
            album: Album to rename
            new_name: New name for the album

        Returns:
            True if successful, False otherwise
        """
        # Validate new name
        if not self._is_valid_album_name(new_name):
            raise ValueError(f"Invalid album name: {new_name}")

        old_path = album.path
        new_path = old_path.parent / new_name

        if new_path.exists():
            raise ValueError(f"Album with name '{new_name}' already exists")

        try:
            # Rename directory
            old_path.rename(new_path)

            # Update album object
            old_path_str = str(old_path)
            album.path = new_path
            album.name = new_name
            album.date = Album.parse_date_from_name(new_name)

            # Update custom ordering (update path key)
            if old_path_str in self._custom_order:
                sort_index = self._custom_order.pop(old_path_str)
                self._custom_order[str(new_path)] = sort_index
                self._save_custom_ordering()

            # Notify observers
            self._notify_albums_changed()

            return True

        except OSError as e:
            print(f"Error: Could not rename album: {e}")
            return False

    def delete_album(self, album: Album, delete_files: bool = False) -> bool:
        """Delete an album.

        Args:
            album: Album to delete
            delete_files: Whether to delete the directory and files

        Returns:
            True if successful, False otherwise
        """
        try:
            # Remove from albums list
            self._albums.remove(album)

            # Remove from custom ordering
            album_path_str = str(album.path)
            if album_path_str in self._custom_order:
                self._custom_order.pop(album_path_str)
                self._save_custom_ordering()

            # Delete directory if requested
            if delete_files and album.path.exists():
                import shutil
                shutil.rmtree(album.path)

            # Notify observers
            self._notify_albums_changed()

            return True

        except (ValueError, OSError) as e:
            print(f"Error: Could not delete album: {e}")
            return False

    def _is_valid_album_name(self, name: str) -> bool:
        """Validate album name.

        Args:
            name: Album name to validate

        Returns:
            True if valid, False otherwise
        """
        # Use FileValidator for comprehensive validation
        is_valid, _ = FileValidator.validate_album_name(name)
        return is_valid

    # ==================== Observer Pattern ====================

    def _notify_albums_changed(self):
        """Notify observers that albums have changed."""
        if self.on_albums_changed:
            self.on_albums_changed(self._albums.copy())

    def set_albums_changed_callback(self, callback: Callable[[List[Album]], None]):
        """Set callback for when albums change.

        Args:
            callback: Function to call with updated album list
        """
        self.on_albums_changed = callback

    # ==================== Statistics ====================

    def get_album_count(self) -> int:
        """Get count of albums.

        Returns:
            Number of albums
        """
        return len(self._albums)

    def get_total_photo_count(self) -> int:
        """Get total count of photos across all albums.

        Returns:
            Total number of photos
        """
        return sum(album.photo_count for album in self._albums)

    # ==================== Photo Loading (Lazy) ====================

    def load_photos(self, album: Album, force_reload: bool = False) -> List[Photo]:
        """Load photos for an album (lazy loading).

        Photos are cached after first load to avoid repeated scanning.

        Args:
            album: Album to load photos for
            force_reload: Force reload even if cached

        Returns:
            List of Photo objects
        """
        album_path_str = str(album.path)

        # Check cache
        if not force_reload and album_path_str in self._photo_cache:
            return self._photo_cache[album_path_str].copy()

        # Scan album directory for photos
        photos = self._scan_photos_in_album(album)

        # Cache photos
        self._photo_cache[album_path_str] = photos

        # Update album's photo list
        album.photos = photos

        return photos.copy()

    def _scan_photos_in_album(self, album: Album) -> List[Photo]:
        """Scan album directory for photo files.

        Args:
            album: Album to scan

        Returns:
            List of Photo objects
        """
        supported_formats = {'.jpg', '.jpeg', '.png', '.heic', '.cr3', '.cr2', '.nef', '.arw', '.dng', '.raw'}

        photos = []

        if not album.path.exists() or not album.path.is_dir():
            return photos

        # Scan directory
        for file_path in sorted(album.path.iterdir()):
            if not file_path.is_file():
                continue

            if file_path.suffix.lower() in supported_formats:
                photo = Photo(path=file_path)
                photos.append(photo)

        return photos

    def load_photos_with_deduplication(
        self,
        album: Album,
        force_reload: bool = False
    ) -> List[PhotoPair]:
        """Load photos with RAW-JPEG deduplication.

        Args:
            album: Album to load photos for
            force_reload: Force reload even if cached

        Returns:
            List of PhotoPair objects (deduplicated)
        """
        # Load raw photos
        photos = self.load_photos(album, force_reload)

        # Deduplicate using PhotoPair
        pairs = PhotoPair.detect_pairs(photos)

        return pairs

    def generate_thumbnails_for_album(
        self,
        album: Album,
        photos: Optional[List[Photo]] = None
    ) -> int:
        """Generate thumbnails for all photos in an album.

        Args:
            album: Album to generate thumbnails for
            photos: Optional list of photos (if already loaded)

        Returns:
            Number of thumbnails successfully generated
        """
        if not self.photo_processor:
            return 0

        # Load photos if not provided
        if photos is None:
            photos = self.load_photos(album)

        success_count = 0

        for photo in photos:
            try:
                thumbnail_path = self.photo_processor.generate_thumbnail(photo.path)
                if thumbnail_path:
                    photo.thumbnail_path = thumbnail_path
                    success_count += 1
            except Exception as e:
                print(f"Warning: Could not generate thumbnail for {photo.filename}: {e}")

        return success_count

    def invalidate_photo_cache(self, album: Optional[Album] = None):
        """Invalidate photo cache.

        Args:
            album: Specific album to invalidate, or None for all albums
        """
        if album:
            album_path_str = str(album.path)
            self._photo_cache.pop(album_path_str, None)
        else:
            self._photo_cache.clear()

    def _generate_album_thumbnails(self):
        """Generate thumbnails for all albums (using first photo)."""
        if not self.photo_processor:
            return

        for album in self._albums:
            if album.photo_count > 0:
                # Load first photo
                photos = self._scan_photos_in_album(album)
                if len(photos) > 0:
                    first_photo = photos[0]
                    try:
                        # Generate album preview thumbnail
                        thumbnail_path = self.photo_processor.generate_album_preview(first_photo.path)
                        if thumbnail_path:
                            album.thumbnail_path = thumbnail_path
                    except Exception as e:
                        print(f"Warning: Could not generate album thumbnail for {album.name}: {e}")

    def __str__(self) -> str:
        """String representation."""
        return f"AlbumManager({len(self._albums)} albums)"
