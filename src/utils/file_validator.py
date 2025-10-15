"""File and album name validation utilities.

This module provides validation for album and photo names to ensure they are
safe for filesystem operations across different operating systems.
"""

import re
from pathlib import Path
from typing import Optional


class FileValidator:
    """Validator for filenames and album names."""

    # Invalid characters for filesystem paths (Windows + Unix)
    INVALID_CHARS = {'/', '\\', ':', '*', '?', '"', '<', '>', '|', '\0'}

    # Pattern to match any invalid character
    INVALID_PATTERN = re.compile(r'[/\\:*?"<>|\x00]')

    # Reserved names on Windows
    RESERVED_NAMES = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }

    @staticmethod
    def is_valid_album_name(name: str) -> bool:
        """Check if album name is valid for filesystem.

        Args:
            name: Proposed album name

        Returns:
            True if name is valid
        """
        if not name or not name.strip():
            return False

        # Check for invalid characters
        if FileValidator.INVALID_PATTERN.search(name):
            return False

        # Check for reserved names (Windows)
        if name.upper() in FileValidator.RESERVED_NAMES:
            return False

        # Check for names that are just dots or spaces
        if name.strip('.').strip() == '':
            return False

        # Check length (most filesystems have 255 char limit)
        if len(name.encode('utf-8')) > 255:
            return False

        return True

    @staticmethod
    def validate_album_name(name: str) -> tuple[bool, Optional[str]]:
        """Validate album name and provide error message if invalid.

        Args:
            name: Proposed album name

        Returns:
            Tuple of (is_valid, error_message)
            error_message is None if valid
        """
        if not name or not name.strip():
            return False, "Album name cannot be empty"

        if FileValidator.INVALID_PATTERN.search(name):
            invalid_chars = [c for c in FileValidator.INVALID_CHARS if c in name]
            return False, f"Album name contains invalid characters: {', '.join(invalid_chars)}"

        if name.upper() in FileValidator.RESERVED_NAMES:
            return False, f"Album name '{name}' is a reserved system name"

        if name.strip('.').strip() == '':
            return False, "Album name cannot consist only of dots and spaces"

        if len(name.encode('utf-8')) > 255:
            return False, "Album name is too long (max 255 bytes)"

        return True, None

    @staticmethod
    def sanitize_album_name(name: str, replacement: str = '_') -> str:
        """Sanitize album name by replacing invalid characters.

        Args:
            name: Original album name
            replacement: Character to replace invalid chars with

        Returns:
            Sanitized album name
        """
        if not name:
            return "Untitled"

        # Replace invalid characters
        sanitized = FileValidator.INVALID_PATTERN.sub(replacement, name)

        # Handle reserved names
        if sanitized.upper() in FileValidator.RESERVED_NAMES:
            sanitized = f"{sanitized}_album"

        # Ensure it's not empty after sanitization
        sanitized = sanitized.strip('.').strip()
        if not sanitized:
            sanitized = "Untitled"

        # Truncate if too long
        if len(sanitized.encode('utf-8')) > 255:
            # Truncate to 255 bytes
            sanitized = sanitized.encode('utf-8')[:255].decode('utf-8', errors='ignore')

        return sanitized

    @staticmethod
    def is_album_name_available(parent_dir: Path, album_name: str) -> bool:
        """Check if album name is available (doesn't already exist).

        Args:
            parent_dir: Parent directory where album would be created
            album_name: Proposed album name

        Returns:
            True if name is available
        """
        album_path = parent_dir / album_name
        return not album_path.exists()

    @staticmethod
    def validate_and_check_availability(
        parent_dir: Path,
        album_name: str
    ) -> tuple[bool, Optional[str]]:
        """Validate album name and check if it's available.

        Args:
            parent_dir: Parent directory where album would be created
            album_name: Proposed album name

        Returns:
            Tuple of (is_valid_and_available, error_message)
        """
        # First validate the name
        is_valid, error_msg = FileValidator.validate_album_name(album_name)
        if not is_valid:
            return False, error_msg

        # Then check availability
        if not FileValidator.is_album_name_available(parent_dir, album_name):
            return False, f"Album '{album_name}' already exists"

        return True, None

    @staticmethod
    def is_supported_image_format(path: Path) -> bool:
        """Check if file is a supported image format.

        Args:
            path: Path to file

        Returns:
            True if file format is supported
        """
        supported_formats = {
            '.jpg', '.jpeg', '.png', '.heic', '.heif',  # Standard
            '.cr3', '.cr2', '.nef', '.arw', '.dng', '.raw'  # RAW
        }
        return path.suffix.lower() in supported_formats

    @staticmethod
    def get_file_base_name(filename: str) -> str:
        """Get base name without extension (for RAW-JPEG pairing).

        Args:
            filename: File name with extension

        Returns:
            Base name without extension
        """
        path = Path(filename)
        return path.stem

    @staticmethod
    def are_paired_files(file1: Path, file2: Path) -> bool:
        """Check if two files are a RAW-JPEG pair (same base name).

        Args:
            file1: First file path
            file2: Second file path

        Returns:
            True if files have same base name and different extensions
        """
        if file1.stem != file2.stem:
            return False

        ext1 = file1.suffix.lower()
        ext2 = file2.suffix.lower()

        # Check if one is RAW and one is JPEG
        raw_exts = {'.cr3', '.cr2', '.nef', '.arw', '.dng', '.raw'}
        jpeg_exts = {'.jpg', '.jpeg'}

        is_pair = (
            (ext1 in raw_exts and ext2 in jpeg_exts) or
            (ext1 in jpeg_exts and ext2 in raw_exts)
        )

        return is_pair
