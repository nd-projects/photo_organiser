"""EXIF metadata extraction for JPEG, PNG, and RAW formats.

This module handles EXIF data extraction from various image formats including
RAW files (CR3, NEF, ARW, DNG) using rawpy and standard formats using exifread.
"""

import io
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import exifread
except ImportError:
    exifread = None

try:
    import rawpy
except ImportError:
    rawpy = None


class EXIFParser:
    """EXIF metadata parser for images."""

    # RAW format extensions
    RAW_FORMATS = {'.cr3', '.nef', '.arw', '.dng', '.cr2', '.raw'}

    # Standard image formats
    STANDARD_FORMATS = {'.jpg', '.jpeg', '.png', '.heic', '.heif'}

    @staticmethod
    def is_raw_format(path: Path) -> bool:
        """Check if file is a RAW format.

        Args:
            path: Path to image file

        Returns:
            True if file is RAW format
        """
        return path.suffix.lower() in EXIFParser.RAW_FORMATS

    @staticmethod
    def is_supported_format(path: Path) -> bool:
        """Check if file format is supported for EXIF extraction.

        Args:
            path: Path to image file

        Returns:
            True if format is supported
        """
        suffix = path.suffix.lower()
        return suffix in EXIFParser.RAW_FORMATS or suffix in EXIFParser.STANDARD_FORMATS

    @staticmethod
    def extract_date(path: Path) -> Optional[datetime]:
        """Extract date from EXIF metadata.

        Tries to extract DateTimeOriginal, then falls back to DateTime.

        Args:
            path: Path to image file

        Returns:
            Datetime object if found, None otherwise
        """
        if not path.exists():
            return None

        try:
            if EXIFParser.is_raw_format(path):
                return EXIFParser._extract_date_raw(path)
            else:
                return EXIFParser._extract_date_standard(path)
        except Exception as e:
            # Log warning but don't crash
            print(f"Warning: Could not extract EXIF date from {path}: {e}")
            return None

    @staticmethod
    def _extract_date_raw(path: Path) -> Optional[datetime]:
        """Extract date from RAW file using rawpy.

        Args:
            path: Path to RAW image file

        Returns:
            Datetime object if found, None otherwise
        """
        if rawpy is None:
            return None

        try:
            with rawpy.imread(str(path)) as raw:
                # Try to get DateTimeOriginal from metadata
                if hasattr(raw, 'metadata'):
                    metadata = raw.metadata
                    if hasattr(metadata, 'timestamp'):
                        # rawpy timestamp is a datetime object
                        return metadata.timestamp
        except Exception:
            pass

        return None

    @staticmethod
    def _extract_date_standard(path: Path) -> Optional[datetime]:
        """Extract date from standard image format using exifread.

        Args:
            path: Path to image file

        Returns:
            Datetime object if found, None otherwise
        """
        if exifread is None:
            return None

        try:
            with open(path, 'rb') as f:
                tags = exifread.process_file(f, stop_tag='DateTimeOriginal')

                # Try DateTimeOriginal first (when photo was taken)
                if 'EXIF DateTimeOriginal' in tags:
                    date_str = str(tags['EXIF DateTimeOriginal'])
                    return EXIFParser._parse_exif_datetime(date_str)

                # Fall back to DateTime (when file was modified)
                if 'Image DateTime' in tags:
                    date_str = str(tags['Image DateTime'])
                    return EXIFParser._parse_exif_datetime(date_str)

        except Exception:
            pass

        return None

    @staticmethod
    def _parse_exif_datetime(date_str: str) -> Optional[datetime]:
        """Parse EXIF datetime string to datetime object.

        EXIF format: 'YYYY:MM:DD HH:MM:SS'

        Args:
            date_str: EXIF datetime string

        Returns:
            Datetime object if parsing succeeds, None otherwise
        """
        try:
            return datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
        except ValueError:
            return None

    @staticmethod
    def extract_dimensions(path: Path) -> Optional[tuple[int, int]]:
        """Extract image dimensions from EXIF or file.

        Args:
            path: Path to image file

        Returns:
            Tuple of (width, height) if found, None otherwise
        """
        if not path.exists():
            return None

        try:
            if EXIFParser.is_raw_format(path):
                return EXIFParser._extract_dimensions_raw(path)
            else:
                return EXIFParser._extract_dimensions_standard(path)
        except Exception:
            return None

    @staticmethod
    def _extract_dimensions_raw(path: Path) -> Optional[tuple[int, int]]:
        """Extract dimensions from RAW file.

        Args:
            path: Path to RAW file

        Returns:
            Tuple of (width, height) if found, None otherwise
        """
        if rawpy is None:
            return None

        try:
            with rawpy.imread(str(path)) as raw:
                # Get raw sizes
                sizes = raw.sizes
                return (sizes.width, sizes.height)
        except Exception:
            return None

    @staticmethod
    def _extract_dimensions_standard(path: Path) -> Optional[tuple[int, int]]:
        """Extract dimensions from standard image format.

        Args:
            path: Path to image file

        Returns:
            Tuple of (width, height) if found, None otherwise
        """
        if exifread is None:
            return None

        try:
            with open(path, 'rb') as f:
                tags = exifread.process_file(f, stop_tag='ExifImageWidth')

                width = None
                height = None

                if 'EXIF ExifImageWidth' in tags:
                    width = int(str(tags['EXIF ExifImageWidth']))
                if 'EXIF ExifImageLength' in tags:
                    height = int(str(tags['EXIF ExifImageLength']))

                if width and height:
                    return (width, height)

        except Exception:
            pass

        return None

    @staticmethod
    def extract_all(path: Path) -> dict:
        """Extract all available EXIF metadata.

        Args:
            path: Path to image file

        Returns:
            Dictionary with available metadata fields
        """
        metadata = {
            'path': str(path),
            'format': path.suffix.lower(),
            'date': EXIFParser.extract_date(path),
            'dimensions': EXIFParser.extract_dimensions(path),
        }

        return metadata
