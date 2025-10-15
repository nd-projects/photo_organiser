"""Photo processing service for thumbnails and image operations.

This module handles thumbnail generation, RAW image preview extraction,
and image format conversions.
"""

import io
from pathlib import Path
from typing import Optional, Tuple

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import rawpy
except ImportError:
    rawpy = None

from ..utils.thumbnail_cache import ThumbnailCache
from ..models.photo import Photo, PhotoPair


class PhotoProcessor:
    """Service for photo processing operations."""

    # Standard thumbnail sizes
    ALBUM_PREVIEW_SIZE = (200, 200)
    PHOTO_TILE_SIZE = (150, 150)

    def __init__(self, cache_dir: Path):
        """Initialize photo processor with cache directory.

        Args:
            cache_dir: Directory for thumbnail cache

        Raises:
            ImportError: If PIL/Pillow is not available
        """
        if Image is None:
            raise ImportError("Pillow is required for photo processing")

        self.cache = ThumbnailCache(cache_dir)

    def generate_thumbnail(
        self,
        source_path: Path,
        size: Tuple[int, int] = PHOTO_TILE_SIZE
    ) -> Optional[Path]:
        """Generate and cache a thumbnail for an image.

        Args:
            source_path: Path to source image file
            size: Thumbnail size as (width, height)

        Returns:
            Path to cached thumbnail or None on error
        """
        # Check if cached thumbnail exists and is valid
        cached_path = self.cache.get(source_path, size)
        if cached_path:
            return cached_path

        try:
            # Load image (handles RAW formats)
            img = self._load_image_for_thumbnail(source_path)

            # Generate thumbnail
            img.thumbnail(size, Image.Resampling.LANCZOS)

            # Get cache path and save
            cache_path = self.cache.put(source_path, size)
            img.save(cache_path, "JPEG", quality=85, optimize=True)

            return cache_path

        except Exception as e:
            print(f"Error generating thumbnail for {source_path}: {e}")
            return None

    def _load_image_for_thumbnail(self, path: Path) -> Image.Image:
        """Load image for thumbnail generation, handling RAW formats.

        Args:
            path: Path to image file

        Returns:
            PIL Image object

        Raises:
            Exception: If image cannot be loaded
        """
        suffix = path.suffix.lower()

        if suffix in ['.cr3', '.cr2', '.nef', '.arw', '.dng', '.raw']:
            # RAW format - use rawpy
            return self._extract_raw_preview(path)
        else:
            # Standard format - use PIL directly
            return Image.open(path)

    def _extract_raw_preview(self, path: Path) -> Image.Image:
        """Extract embedded preview from RAW file.

        This is much faster than full RAW decoding (10-100x speedup).

        Args:
            path: Path to RAW image file

        Returns:
            PIL Image object

        Raises:
            Exception: If preview cannot be extracted
        """
        if rawpy is None:
            raise ImportError("rawpy is required for RAW image support")

        with rawpy.imread(str(path)) as raw:
            try:
                # Try to extract embedded JPEG preview (fast)
                thumb = raw.extract_thumb()
                if thumb.format == rawpy.ThumbFormat.JPEG:
                    return Image.open(io.BytesIO(thumb.data))
            except Exception:
                # Preview extraction failed, fall back to full decode
                pass

            # Fallback: decode full RAW (slow but correct)
            rgb = raw.postprocess()
            return Image.fromarray(rgb)

    def detect_raw_jpeg_pairs(self, photos: list[Photo]) -> list[PhotoPair]:
        """Detect and group RAW-JPEG pairs from photo list.

        Args:
            photos: List of Photo objects

        Returns:
            List of PhotoPair objects
        """
        return PhotoPair.detect_pairs(photos)

    def generate_album_preview(
        self,
        first_photo_path: Path
    ) -> Optional[Path]:
        """Generate album preview thumbnail from first photo.

        Args:
            first_photo_path: Path to first photo in album

        Returns:
            Path to generated thumbnail or None
        """
        return self.generate_thumbnail(first_photo_path, self.ALBUM_PREVIEW_SIZE)

    def get_image_dimensions(self, path: Path) -> Optional[Tuple[int, int]]:
        """Get image dimensions without loading full image.

        Args:
            path: Path to image file

        Returns:
            Tuple of (width, height) or None
        """
        try:
            if path.suffix.lower() in ['.cr3', '.cr2', '.nef', '.arw', '.dng', '.raw']:
                return self._get_raw_dimensions(path)
            else:
                with Image.open(path) as img:
                    return img.size
        except Exception:
            return None

    def _get_raw_dimensions(self, path: Path) -> Optional[Tuple[int, int]]:
        """Get RAW image dimensions.

        Args:
            path: Path to RAW file

        Returns:
            Tuple of (width, height) or None
        """
        if rawpy is None:
            return None

        try:
            with rawpy.imread(str(path)) as raw:
                sizes = raw.sizes
                return (sizes.width, sizes.height)
        except Exception:
            return None

    def is_corrupted(self, path: Path) -> bool:
        """Check if an image file is corrupted.

        Args:
            path: Path to image file

        Returns:
            True if file appears corrupted
        """
        try:
            img = self._load_image_for_thumbnail(path)
            # Try to load image data
            img.load()
            return False
        except Exception:
            return True

    def invalidate_thumbnail(
        self,
        source_path: Path,
        size: Optional[Tuple[int, int]] = None
    ) -> None:
        """Invalidate cached thumbnail for a photo.

        Args:
            source_path: Path to source image
            size: Specific size to invalidate, or None for all sizes
        """
        self.cache.invalidate(source_path, size)

    def get_cache_stats(self) -> dict:
        """Get thumbnail cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return self.cache.get_cache_stats()

    def clear_cache(self) -> int:
        """Clear entire thumbnail cache.

        Returns:
            Number of files deleted
        """
        return self.cache.clear()
