"""PhotoManager service for photo operations (move, delete, etc.).

This service handles file operations on photos with atomicity guarantees,
RAW-JPEG pair handling, and proper error handling/rollback.
"""

import shutil
from pathlib import Path
from typing import Optional

from src.services.filesystem_scanner import FilesystemScanner


class PhotoManager:
    """Manages photo operations with filesystem integration.

    Responsibilities:
    - Move photos between albums with atomic operations
    - Detect and move RAW-JPEG pairs together
    - Rollback on failure to prevent data loss
    - Validate operations before executing
    """

    # Supported RAW formats
    RAW_FORMATS = {".cr3", ".cr2", ".nef", ".arw", ".dng", ".raw"}

    # Supported image formats
    IMAGE_FORMATS = {".jpg", ".jpeg", ".png", ".heic", ".bmp"} | RAW_FORMATS

    def __init__(self, scanner: FilesystemScanner):
        """Initialize PhotoManager.

        Args:
            scanner: Filesystem scanner for album discovery
        """
        self.scanner = scanner

    def move_photos(self, photo_paths: list[Path], destination_album: Path) -> dict:
        """Move photos to destination album with atomic operation and rollback.

        This method:
        1. Validates inputs (photos exist, destination exists, no conflicts)
        2. Detects RAW-JPEG pairs and ensures both files move together
        3. Performs atomic move with rollback on any failure
        4. Returns detailed result with success/error information

        Args:
            photo_paths: List of photo file paths to move
            destination_album: Destination album directory path

        Returns:
            Dictionary with:
                - success: bool - Overall operation success
                - moved_count: int - Number of files moved
                - error: str - Error message if failed
                - moved_files: list[Path] - List of successfully moved files
        """
        # Validate inputs
        validation_result = self._validate_move_operation(
            photo_paths, destination_album
        )
        if not validation_result["valid"]:
            return {
                "success": False,
                "moved_count": 0,
                "error": validation_result["error"],
                "moved_files": [],
            }

        # Detect pairs and build complete file list
        files_to_move = self._detect_and_expand_pairs(photo_paths)

        # Check for conflicts in destination
        conflict_result = self._check_conflicts(files_to_move, destination_album)
        if not conflict_result["no_conflicts"]:
            return {
                "success": False,
                "moved_count": 0,
                "error": conflict_result["error"],
                "moved_files": [],
            }

        # Execute atomic move with rollback capability
        return self._execute_atomic_move(files_to_move, destination_album)

    def _validate_move_operation(
        self, photo_paths: list[Path], destination_album: Path
    ) -> dict:
        """Validate move operation inputs.

        Args:
            photo_paths: List of photo paths to validate
            destination_album: Destination directory to validate

        Returns:
            Dictionary with 'valid' bool and 'error' message
        """
        # Check for empty list
        if not photo_paths:
            return {"valid": False, "error": "No photos selected to move"}

        # Check destination exists
        if not destination_album.exists():
            return {
                "valid": False,
                "error": f"Destination album does not exist: {destination_album}",
            }

        if not destination_album.is_dir():
            return {
                "valid": False,
                "error": f"Destination is not a directory: {destination_album}",
            }

        # Check all source files exist
        for photo_path in photo_paths:
            if not photo_path.exists():
                return {
                    "valid": False,
                    "error": f"Source file does not exist: {photo_path}",
                }

            if not photo_path.is_file():
                return {"valid": False, "error": f"Source is not a file: {photo_path}"}

        return {"valid": True, "error": None}

    def _detect_and_expand_pairs(self, photo_paths: list[Path]) -> list[Path]:
        """Detect RAW-JPEG pairs and expand file list to include both files.

        For each photo, check if it has a corresponding RAW or JPEG pair.
        If found, add the pair to the list of files to move.

        Args:
            photo_paths: List of selected photo paths

        Returns:
            Expanded list of file paths including detected pairs
        """
        files_to_move = []
        processed_bases = set()  # Track base names to avoid duplicates

        for photo_path in photo_paths:
            base_name = photo_path.stem
            extension = photo_path.suffix.lower()

            # Skip if we've already processed this base name
            if base_name in processed_bases:
                continue

            processed_bases.add(base_name)

            # Add the selected file
            files_to_move.append(photo_path)

            # Look for pair
            parent_dir = photo_path.parent

            if extension in self.RAW_FORMATS:
                # RAW file selected - look for JPEG pair
                for jpeg_ext in [".jpg", ".jpeg"]:
                    jpeg_pair = parent_dir / f"{base_name}{jpeg_ext}"
                    if jpeg_pair.exists() and jpeg_pair not in files_to_move:
                        files_to_move.append(jpeg_pair)
                        break

            elif extension in {".jpg", ".jpeg"}:
                # JPEG file selected - look for RAW pair
                for raw_ext in self.RAW_FORMATS:
                    raw_pair = parent_dir / f"{base_name}{raw_ext}"
                    if raw_pair.exists() and raw_pair not in files_to_move:
                        files_to_move.append(raw_pair)
                        break

        return files_to_move

    def _check_conflicts(
        self, files_to_move: list[Path], destination_album: Path
    ) -> dict:
        """Check for filename conflicts in destination.

        Args:
            files_to_move: List of files to check
            destination_album: Destination directory

        Returns:
            Dictionary with 'no_conflicts' bool and 'error' message
        """
        for file_path in files_to_move:
            dest_path = destination_album / file_path.name

            if dest_path.exists():
                return {
                    "no_conflicts": False,
                    "error": f"File already exists in destination: {file_path.name}",
                }

        return {"no_conflicts": True, "error": None}

    def _execute_atomic_move(
        self, files_to_move: list[Path], destination_album: Path
    ) -> dict:
        """Execute atomic move operation with rollback on failure.

        Strategy:
        1. Move all files to destination
        2. If any move fails, rollback all previously moved files
        3. Return success/failure with details

        Args:
            files_to_move: List of files to move
            destination_album: Destination directory

        Returns:
            Result dictionary with success, moved_count, error, moved_files
        """
        moved_files = []

        try:
            # Move each file
            for file_path in files_to_move:
                dest_path = destination_album / file_path.name

                # Use shutil.move for atomic operation
                shutil.move(str(file_path), str(dest_path))
                moved_files.append((file_path, dest_path))

            # Success - all files moved
            return {
                "success": True,
                "moved_count": len(moved_files),
                "error": None,
                "moved_files": [dest for _, dest in moved_files],
            }

        except Exception as e:
            # Rollback: move all successfully moved files back to source
            self._rollback_moves(moved_files)

            return {
                "success": False,
                "moved_count": 0,
                "error": f"Move operation failed: {str(e)}",
                "moved_files": [],
            }

    def _rollback_moves(self, moved_files: list[tuple[Path, Path]]):
        """Rollback moved files by moving them back to source.

        Args:
            moved_files: List of (source_path, dest_path) tuples
        """
        for source_path, dest_path in moved_files:
            try:
                if dest_path.exists():
                    # Move back to original location
                    shutil.move(str(dest_path), str(source_path))
            except Exception as e:
                # Log error but continue rollback
                print(f"Warning: Failed to rollback {dest_path}: {e}")

    def get_photo_pair(self, photo_path: Path) -> Optional[Path]:
        """Get the pair file for a photo (RAW or JPEG).

        Args:
            photo_path: Path to photo file

        Returns:
            Path to pair file if found, None otherwise
        """
        base_name = photo_path.stem
        extension = photo_path.suffix.lower()
        parent_dir = photo_path.parent

        if extension in self.RAW_FORMATS:
            # Look for JPEG pair
            for jpeg_ext in [".jpg", ".jpeg"]:
                jpeg_pair = parent_dir / f"{base_name}{jpeg_ext}"
                if jpeg_pair.exists():
                    return jpeg_pair

        elif extension in {".jpg", ".jpeg"}:
            # Look for RAW pair
            for raw_ext in self.RAW_FORMATS:
                raw_pair = parent_dir / f"{base_name}{raw_ext}"
                if raw_pair.exists():
                    return raw_pair

        return None

    def is_raw_format(self, file_path: Path) -> bool:
        """Check if file is a RAW format.

        Args:
            file_path: Path to file

        Returns:
            True if file is RAW format
        """
        return file_path.suffix.lower() in self.RAW_FORMATS

    def is_image_format(self, file_path: Path) -> bool:
        """Check if file is a supported image format.

        Args:
            file_path: Path to file

        Returns:
            True if file is supported image format
        """
        return file_path.suffix.lower() in self.IMAGE_FORMATS
