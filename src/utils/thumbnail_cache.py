"""Thumbnail caching utility with SHA-256 key generation.

This module provides disk-based thumbnail caching to avoid regenerating
thumbnails for the same source files.
"""

import hashlib
from pathlib import Path
from typing import Optional


class ThumbnailCache:
    """Disk-based thumbnail cache manager.

    Uses SHA-256 hash of source file path as cache key to ensure uniqueness
    and avoid filesystem path limitations.
    """

    def __init__(self, cache_dir: Path):
        """Initialize thumbnail cache.

        Args:
            cache_dir: Directory to store cached thumbnails

        Raises:
            ValueError: If cache_dir is not writable
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        if not self.cache_dir.is_dir():
            raise ValueError(f"Cache directory is not a directory: {self.cache_dir}")

    def _generate_cache_key(self, source_path: Path) -> str:
        """Generate SHA-256 based cache key from source path.

        Args:
            source_path: Path to source image file

        Returns:
            Hex digest of SHA-256 hash
        """
        path_str = str(source_path.resolve())
        return hashlib.sha256(path_str.encode("utf-8")).hexdigest()

    def get_cache_path(self, source_path: Path, size: tuple[int, int]) -> Path:
        """Get the cache file path for a given source and size.

        Args:
            source_path: Path to source image file
            size: Thumbnail size as (width, height)

        Returns:
            Path to cached thumbnail file
        """
        cache_key = self._generate_cache_key(source_path)
        filename = f"{cache_key}_{size[0]}x{size[1]}.jpg"
        return self.cache_dir / filename

    def is_cached(self, source_path: Path, size: tuple[int, int]) -> bool:
        """Check if a valid cached thumbnail exists.

        A cached thumbnail is valid if:
        1. It exists
        2. Its modification time is >= source file modification time

        Args:
            source_path: Path to source image file
            size: Thumbnail size as (width, height)

        Returns:
            True if valid cached thumbnail exists
        """
        cache_path = self.get_cache_path(source_path, size)

        if not cache_path.exists():
            return False

        # Check if cache is newer than source
        try:
            cache_mtime = cache_path.stat().st_mtime
            source_mtime = source_path.stat().st_mtime
            return cache_mtime >= source_mtime
        except OSError:
            # If we can't stat either file, consider it not cached
            return False

    def get(self, source_path: Path, size: tuple[int, int]) -> Optional[Path]:
        """Get cached thumbnail path if it exists and is valid.

        Args:
            source_path: Path to source image file
            size: Thumbnail size as (width, height)

        Returns:
            Path to cached thumbnail if valid, None otherwise
        """
        if self.is_cached(source_path, size):
            return self.get_cache_path(source_path, size)
        return None

    def put(self, source_path: Path, size: tuple[int, int]) -> Path:
        """Get the path where a thumbnail should be saved.

        This doesn't create the thumbnail, just returns where it should be stored.

        Args:
            source_path: Path to source image file
            size: Thumbnail size as (width, height)

        Returns:
            Path where thumbnail should be saved
        """
        return self.get_cache_path(source_path, size)

    def invalidate(
        self, source_path: Path, size: Optional[tuple[int, int]] = None
    ) -> None:
        """Remove cached thumbnail(s) for a source file.

        Args:
            source_path: Path to source image file
            size: Specific size to invalidate, or None to remove all sizes
        """
        if size is not None:
            # Remove specific size
            cache_path = self.get_cache_path(source_path, size)
            if cache_path.exists():
                cache_path.unlink()
        else:
            # Remove all thumbnails for this source
            cache_key = self._generate_cache_key(source_path)
            pattern = f"{cache_key}_*.jpg"
            for cache_file in self.cache_dir.glob(pattern):
                cache_file.unlink()

    def clear(self) -> int:
        """Clear entire thumbnail cache.

        Returns:
            Number of files deleted
        """
        count = 0
        for cache_file in self.cache_dir.glob("*.jpg"):
            cache_file.unlink()
            count += 1
        return count

    def get_cache_size(self) -> int:
        """Get total size of cache in bytes.

        Returns:
            Total size of all cached thumbnails in bytes
        """
        total_size = 0
        for cache_file in self.cache_dir.glob("*.jpg"):
            try:
                total_size += cache_file.stat().st_size
            except OSError:
                pass
        return total_size

    def get_cache_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats (count, size_bytes, size_mb)
        """
        count = 0
        total_size = 0

        for cache_file in self.cache_dir.glob("*.jpg"):
            count += 1
            try:
                total_size += cache_file.stat().st_size
            except OSError:
                pass

        return {
            "count": count,
            "size_bytes": total_size,
            "size_mb": round(total_size / (1024 * 1024), 2),
        }
