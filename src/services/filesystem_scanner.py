"""Filesystem scanner for discovering photo albums.

This module scans a root directory to discover photo albums (subdirectories)
and photos within them. Enforces flat hierarchy (no nested albums).
"""

from pathlib import Path
from typing import List, Optional

from ..models.album import Album
from ..models.photo import Photo
from ..utils.file_validator import FileValidator


class FilesystemScanner:
    """Scanner for discovering albums and photos from filesystem."""

    def __init__(self, root_dir: Path):
        """Initialize scanner with root photo directory.

        Args:
            root_dir: Root directory containing photo albums

        Raises:
            ValueError: If root_dir doesn't exist or isn't a directory
        """
        self.root_dir = Path(root_dir)

        if not self.root_dir.exists():
            raise ValueError(f"Root directory does not exist: {self.root_dir}")

        if not self.root_dir.is_dir():
            raise ValueError(f"Root path is not a directory: {self.root_dir}")

    def scan_albums(self) -> List[Album]:
        """Scan root directory for photo albums.

        Albums are subdirectories of the root directory.
        Enforces flat hierarchy - nested subdirectories are not treated as albums.

        Returns:
            List of Album objects
        """
        albums = []

        try:
            for item in self.root_dir.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    # Create album object
                    album = Album(path=item)

                    # Quick count of photos (don't load them yet)
                    album.photo_count = self._count_photos_in_directory(item)

                    albums.append(album)

        except PermissionError as e:
            print(f"Warning: Permission denied scanning {self.root_dir}: {e}")

        return albums

    def _count_photos_in_directory(self, directory: Path) -> int:
        """Count photo files in a directory (non-recursive).

        Args:
            directory: Directory to scan

        Returns:
            Number of supported image files
        """
        count = 0
        try:
            for item in directory.iterdir():
                if item.is_file() and FileValidator.is_supported_image_format(item):
                    count += 1
        except PermissionError:
            pass

        return count

    def scan_photos_in_album(self, album_path: Path) -> List[Photo]:
        """Scan an album directory for photo files.

        Args:
            album_path: Path to album directory

        Returns:
            List of Photo objects
        """
        photos = []

        if not album_path.exists() or not album_path.is_dir():
            return photos

        try:
            for item in album_path.iterdir():
                if item.is_file() and FileValidator.is_supported_image_format(item):
                    photo = Photo(path=item)
                    photos.append(photo)

        except PermissionError as e:
            print(f"Warning: Permission denied scanning {album_path}: {e}")

        return photos

    def find_album_by_path(self, album_path: Path) -> Optional[Album]:
        """Find an album by its path.

        Args:
            album_path: Path to album directory

        Returns:
            Album object if found and valid, None otherwise
        """
        album_path = Path(album_path)

        if not album_path.exists() or not album_path.is_dir():
            return None

        # Check if it's a direct child of root (flat hierarchy)
        if album_path.parent != self.root_dir:
            return None

        album = Album(path=album_path)
        album.photo_count = self._count_photos_in_directory(album_path)

        return album

    def is_valid_album_directory(self, directory: Path) -> bool:
        """Check if a directory is a valid album.

        Valid albums are:
        - Direct children of root directory (flat hierarchy)
        - Not hidden (don't start with .)
        - Readable

        Args:
            directory: Directory to check

        Returns:
            True if directory is a valid album
        """
        if not directory.exists() or not directory.is_dir():
            return False

        if directory.name.startswith('.'):
            return False

        # Must be direct child of root (flat hierarchy)
        if directory.parent != self.root_dir:
            return False

        return True

    def get_album_count(self) -> int:
        """Get count of albums in root directory.

        Returns:
            Number of valid album directories
        """
        count = 0
        try:
            for item in self.root_dir.iterdir():
                if self.is_valid_album_directory(item):
                    count += 1
        except PermissionError:
            pass

        return count

    def refresh_album(self, album: Album) -> Album:
        """Refresh an album's metadata from filesystem.

        Args:
            album: Album to refresh

        Returns:
            Updated Album object
        """
        if not album.path.exists():
            raise FileNotFoundError(f"Album directory not found: {album.path}")

        # Update photo count
        album.photo_count = self._count_photos_in_directory(album.path)

        # Update name (in case directory was renamed)
        album.name = album.path.name

        # Re-parse date
        album.date = Album.parse_date_from_name(album.name)

        return album

    def verify_album_exists(self, album_path: Path) -> bool:
        """Verify an album directory still exists.

        Args:
            album_path: Path to album directory

        Returns:
            True if album exists and is valid
        """
        return self.is_valid_album_directory(Path(album_path))
