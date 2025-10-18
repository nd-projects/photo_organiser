"""Photo and PhotoPair models for image management.

Photo represents an individual image file with metadata.
PhotoPair groups RAW and JPEG versions of the same photo for deduplication.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Photo:
    """Individual photo file entity.

    Attributes:
        path: Absolute path to photo file
        filename: File name with extension
        format: File format/extension (lowercase)
        size_bytes: File size in bytes
        thumbnail_path: Path to cached thumbnail
        exif_date: Date from EXIF metadata
        width: Image width in pixels
        height: Image height in pixels
    """

    path: Path
    filename: str = ""
    format: str = ""
    size_bytes: int = 0
    thumbnail_path: Optional[Path] = None
    exif_date: Optional[datetime] = None
    width: Optional[int] = None
    height: Optional[int] = None

    def __post_init__(self):
        """Initialize derived attributes."""
        # Ensure path is Path object
        if not isinstance(self.path, Path):
            self.path = Path(self.path)

        # Set filename if not provided
        if not self.filename:
            self.filename = self.path.name

        # Set format if not provided
        if not self.format:
            self.format = self.path.suffix.lower().lstrip(".")

        # Set size if not provided and file exists
        if self.size_bytes == 0 and self.path.exists():
            try:
                self.size_bytes = self.path.stat().st_size
            except OSError:
                pass

    @property
    def base_name(self) -> str:
        """Get filename without extension (for pairing detection).

        Returns:
            Base filename without extension
        """
        return self.path.stem

    @property
    def is_raw(self) -> bool:
        """Check if photo is a RAW format.

        Returns:
            True if file is RAW format
        """
        raw_formats = {"cr3", "cr2", "nef", "arw", "dng", "raw"}
        return self.format in raw_formats

    @property
    def display_date(self) -> datetime:
        """Get display date (EXIF date or file modification time).

        Returns:
            Datetime for display purposes
        """
        if self.exif_date:
            return self.exif_date

        # Fall back to file modification time
        try:
            mtime = self.path.stat().st_mtime
            return datetime.fromtimestamp(mtime)
        except OSError:
            # If file doesn't exist, return current time
            return datetime.now()

    def load_exif(self, exif_parser) -> dict:
        """Load EXIF metadata from photo file.

        Args:
            exif_parser: EXIF parser utility

        Returns:
            Dictionary of EXIF metadata
        """
        metadata = exif_parser.extract_all(self.path)

        # Update our attributes
        if metadata.get("date"):
            self.exif_date = metadata["date"]

        if metadata.get("dimensions"):
            self.width, self.height = metadata["dimensions"]

        return metadata

    def generate_thumbnail(
        self, thumbnail_generator, size: tuple[int, int] = (150, 150)
    ) -> Optional[Path]:
        """Generate and cache thumbnail for this photo.

        Args:
            thumbnail_generator: Callable that generates thumbnails
            size: Thumbnail size (width, height)

        Returns:
            Path to generated thumbnail or None
        """
        try:
            thumbnail_path = thumbnail_generator(self.path, size=size)
            self.thumbnail_path = thumbnail_path
            return thumbnail_path
        except Exception as e:
            print(f"Warning: Could not generate thumbnail for {self.filename}: {e}")
            return None

    def __str__(self) -> str:
        """String representation."""
        return f"Photo({self.filename}, {self.format}, {self.size_bytes} bytes)"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return f"Photo(path={self.path}, format={self.format}, size={self.size_bytes})"


@dataclass
class PhotoPair:
    """Grouping of RAW and JPEG versions of the same photo.

    Attributes:
        base_name: Common filename without extension
        raw_path: Path to RAW file (CR3, NEF, etc.)
        jpeg_path: Path to JPEG file
    """

    base_name: str
    jpeg_path: Path
    raw_path: Optional[Path] = None

    def __post_init__(self):
        """Validate paths."""
        # Ensure paths are Path objects
        if not isinstance(self.jpeg_path, Path):
            self.jpeg_path = Path(self.jpeg_path)

        if self.raw_path is not None and not isinstance(self.raw_path, Path):
            self.raw_path = Path(self.raw_path)

    @property
    def display_path(self) -> Path:
        """Get preferred path for display (JPEG).

        Returns:
            Path to JPEG file (preferred for thumbnails)
        """
        return self.jpeg_path

    @property
    def has_raw(self) -> bool:
        """Check if pair has RAW version.

        Returns:
            True if RAW path is set
        """
        return self.raw_path is not None

    def get_all_paths(self) -> list[Path]:
        """Get list of all file paths in this pair.

        Returns:
            List containing JPEG and RAW paths (if present)
        """
        paths = [self.jpeg_path]
        if self.raw_path:
            paths.append(self.raw_path)
        return paths

    @staticmethod
    def detect_pairs(photos: list[Photo]) -> list["PhotoPair"]:
        """Group photos by base name to detect RAW-JPEG pairs.

        Args:
            photos: List of Photo objects

        Returns:
            List of PhotoPair objects
        """
        # Group by base name
        pairs_dict = {}

        for photo in photos:
            base = photo.base_name
            if base not in pairs_dict:
                pairs_dict[base] = {"raw": None, "jpeg": None}

            if photo.is_raw:
                pairs_dict[base]["raw"] = photo.path
            else:
                pairs_dict[base]["jpeg"] = photo.path

        # Create PhotoPair objects
        result = []
        for base_name, paths in pairs_dict.items():
            # Only create pairs where we have at least a JPEG
            # (standalone RAW files are treated as regular photos)
            if paths["jpeg"]:
                result.append(
                    PhotoPair(
                        base_name=base_name,
                        jpeg_path=paths["jpeg"],
                        raw_path=paths["raw"],
                    )
                )

        return result

    def __str__(self) -> str:
        """String representation."""
        if self.has_raw:
            return f"PhotoPair({self.base_name}, RAW+JPEG)"
        return f"PhotoPair({self.base_name}, JPEG only)"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return f"PhotoPair(base_name={self.base_name}, jpeg={self.jpeg_path}, raw={self.raw_path})"
