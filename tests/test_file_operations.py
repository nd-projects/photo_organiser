"""Tests for file operations (album creation, renaming, photo moving).

These tests verify critical file operations to prevent data loss and ensure
atomicity of filesystem operations.
"""

import pytest
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

from src.models.app_state import AppState
from src.models.album import Album
from src.services.album_manager import AlbumManager
from src.services.filesystem_scanner import FilesystemScanner
from src.utils.file_validator import FileValidator


@pytest.fixture
def temp_photo_dir(tmp_path):
    """Create temporary photo directory structure."""
    photo_dir = tmp_path / "photos"
    photo_dir.mkdir()

    # Create some test albums
    album1 = photo_dir / "2024-01-15_Test_Album_1"
    album1.mkdir()
    (album1 / "test1.jpg").touch()

    album2 = photo_dir / "2024-02-20_Test_Album_2"
    album2.mkdir()
    (album2 / "test2.jpg").touch()

    return photo_dir


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temporary data directory for app state."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def app_state(temp_photo_dir, temp_data_dir):
    """Create test app state."""
    state_file = temp_data_dir / "app_state.json"
    thumbnail_dir = temp_data_dir / "thumbnails"
    thumbnail_dir.mkdir()

    return AppState(
        photo_dir=temp_photo_dir,
        state_file=state_file,
        thumbnail_cache_dir=thumbnail_dir
    )


@pytest.fixture
def album_manager(app_state):
    """Create album manager for testing."""
    scanner = FilesystemScanner(app_state.photo_dir)
    manager = AlbumManager(app_state, scanner)
    return manager


# ==================== Album Creation Tests ====================

class TestAlbumCreation:
    """Tests for album creation validation and functionality."""

    def test_create_album_with_valid_name(self, album_manager, temp_photo_dir):
        """Test creating an album with a valid name."""
        album_name = "2024-03-10_New_Album"

        # Create album
        album = album_manager.create_album(album_name)

        # Verify album was created
        assert album is not None
        assert album.name == album_name
        assert album.path.exists()
        assert album.path.is_dir()
        assert album.path == temp_photo_dir / album_name

    def test_create_album_with_simple_name(self, album_manager, temp_photo_dir):
        """Test creating an album with a simple name (no date)."""
        album_name = "Vacation Photos"

        # Create album
        album = album_manager.create_album(album_name)

        # Verify album was created
        assert album is not None
        assert album.path.exists()
        assert album.path == temp_photo_dir / album_name

    def test_create_album_with_special_characters(self, album_manager):
        """Test creating an album with special characters in name."""
        album_name = "Trip to Zürich & München"

        # Create album
        album = album_manager.create_album(album_name)

        # Verify album was created
        assert album is not None
        assert album.path.exists()

    def test_create_album_with_invalid_characters_fails(self, album_manager):
        """Test that creating an album with invalid characters fails."""
        invalid_names = [
            "Album/WithSlash",
            "Album\\WithBackslash",
            "Album:WithColon",
            "Album*WithAsterisk",
            "Album?WithQuestion",
            'Album"WithQuote',
            "Album<WithLess",
            "Album>WithGreater",
            "Album|WithPipe"
        ]

        for invalid_name in invalid_names:
            with pytest.raises(ValueError, match="Invalid album name"):
                album_manager.create_album(invalid_name)

    def test_create_album_with_empty_name_fails(self, album_manager):
        """Test that creating an album with empty name fails."""
        with pytest.raises(ValueError, match="Invalid album name"):
            album_manager.create_album("")

        with pytest.raises(ValueError, match="Invalid album name"):
            album_manager.create_album("   ")

    def test_create_album_with_duplicate_name_fails(self, album_manager, temp_photo_dir):
        """Test that creating an album with duplicate name fails."""
        album_name = "2024-01-15_Test_Album_1"  # Already exists

        with pytest.raises(ValueError, match="already exists"):
            album_manager.create_album(album_name)

    def test_create_album_with_reserved_name_fails(self, album_manager):
        """Test that creating an album with reserved system name fails."""
        reserved_names = ["CON", "PRN", "AUX", "NUL", "COM1", "LPT1"]

        for reserved_name in reserved_names:
            with pytest.raises(ValueError, match="Invalid album name"):
                album_manager.create_album(reserved_name)

    def test_create_album_updates_album_list(self, album_manager):
        """Test that creating an album updates the album list."""
        initial_count = album_manager.get_album_count()

        # Create new album
        album_manager.create_album("New_Test_Album")

        # Verify album count increased
        assert album_manager.get_album_count() == initial_count + 1

    def test_create_album_triggers_callback(self, album_manager):
        """Test that creating an album triggers the albums changed callback."""
        callback_called = False
        callback_albums = None

        def callback(albums):
            nonlocal callback_called, callback_albums
            callback_called = True
            callback_albums = albums

        album_manager.set_albums_changed_callback(callback)

        # Create album
        album_manager.create_album("Callback_Test_Album")

        # Verify callback was called
        assert callback_called
        assert callback_albums is not None
        assert len(callback_albums) > 0


# ==================== Album Rename Tests ====================

class TestAlbumRename:
    """Tests for album rename validation and atomicity."""

    def test_rename_album_with_valid_name(self, album_manager, temp_photo_dir):
        """Test renaming an album with a valid name."""
        # Load albums
        albums = album_manager.load_albums()
        album = albums[0]

        old_path = album.path
        new_name = "2024-01-15_Renamed_Album"

        # Rename album
        success = album_manager.rename_album(album, new_name)

        # Verify rename was successful
        assert success is True
        assert not old_path.exists()  # Old path should not exist
        assert album.path.exists()  # New path should exist
        assert album.path == temp_photo_dir / new_name
        assert album.name == new_name

    def test_rename_album_preserves_photos(self, album_manager, temp_photo_dir):
        """Test that renaming an album preserves all photos."""
        # Load albums
        albums = album_manager.load_albums()
        album = albums[0]

        # Get list of photos before rename
        photos_before = list(album.path.glob("*.jpg"))
        photo_names_before = {p.name for p in photos_before}

        # Rename album
        new_name = "2024-01-15_Renamed_With_Photos"
        success = album_manager.rename_album(album, new_name)

        # Verify photos are preserved
        assert success is True
        photos_after = list(album.path.glob("*.jpg"))
        photo_names_after = {p.name for p in photos_after}

        assert len(photos_after) == len(photos_before)
        assert photo_names_after == photo_names_before

    def test_rename_album_with_invalid_characters_fails(self, album_manager):
        """Test that renaming with invalid characters fails."""
        albums = album_manager.load_albums()
        album = albums[0]

        invalid_names = [
            "Album/WithSlash",
            "Album\\WithBackslash",
            "Album:WithColon",
            "Album*WithAsterisk"
        ]

        for invalid_name in invalid_names:
            with pytest.raises(ValueError, match="Invalid album name"):
                album_manager.rename_album(album, invalid_name)

    def test_rename_album_with_duplicate_name_fails(self, album_manager):
        """Test that renaming to an existing name fails."""
        albums = album_manager.load_albums()
        album = albums[0]

        # Try to rename to the name of another existing album
        existing_name = albums[1].name

        with pytest.raises(ValueError, match="already exists"):
            album_manager.rename_album(album, existing_name)

    def test_rename_album_with_empty_name_fails(self, album_manager):
        """Test that renaming with empty name fails."""
        albums = album_manager.load_albums()
        album = albums[0]

        with pytest.raises(ValueError, match="Invalid album name"):
            album_manager.rename_album(album, "")

        with pytest.raises(ValueError, match="Invalid album name"):
            album_manager.rename_album(album, "   ")

    def test_rename_album_updates_custom_order(self, album_manager):
        """Test that renaming an album updates custom order mapping."""
        # Load albums and set custom order
        albums = album_manager.load_albums()
        album_manager.set_custom_order(albums)

        # Rename first album
        album = albums[0]
        old_path_str = str(album.path)
        new_name = "2024-01-15_Renamed_For_Order_Test"

        # Verify old path is in custom order
        assert old_path_str in album_manager._custom_order
        old_sort_index = album_manager._custom_order[old_path_str]

        # Rename album
        success = album_manager.rename_album(album, new_name)
        assert success is True

        # Verify custom order was updated
        new_path_str = str(album.path)
        assert old_path_str not in album_manager._custom_order
        assert new_path_str in album_manager._custom_order
        assert album_manager._custom_order[new_path_str] == old_sort_index

    def test_rename_album_persists_to_state_file(self, album_manager, app_state):
        """Test that renaming an album persists to state file."""
        # Load albums and set custom order
        albums = album_manager.load_albums()
        album_manager.set_custom_order(albums)

        # Rename album
        album = albums[0]
        new_name = "2024-01-15_Renamed_Persistent"
        success = album_manager.rename_album(album, new_name)
        assert success is True

        # Create new manager and load state
        scanner = FilesystemScanner(app_state.photo_dir)
        new_manager = AlbumManager(app_state, scanner)
        new_manager.load_albums()

        # Verify renamed album is in custom order with correct path
        new_path_str = str(album.path)
        assert new_path_str in new_manager._custom_order

    def test_rename_album_updates_date_if_name_has_date(self, album_manager):
        """Test that renaming updates the album's parsed date."""
        albums = album_manager.load_albums()
        album = albums[0]

        # Rename with new date
        new_name = "2025-06-15_New_Date_Album"
        success = album_manager.rename_album(album, new_name)

        assert success is True
        assert album.date is not None
        assert album.date.year == 2025
        assert album.date.month == 6
        assert album.date.day == 15

    def test_rename_album_atomicity_on_filesystem_error(self, album_manager):
        """Test that rename operation is atomic (no partial changes on error)."""
        albums = album_manager.load_albums()
        album = albums[0]

        old_path = album.path
        old_name = album.name
        new_name = "2024-01-15_Should_Fail_Rename"

        # Mock the rename operation to fail
        with patch.object(Path, 'rename', side_effect=OSError("Simulated filesystem error")):
            success = album_manager.rename_album(album, new_name)

            # Verify rename failed
            assert success is False

            # Verify album state was not changed
            assert album.path == old_path
            assert album.name == old_name
            assert old_path.exists()

    def test_rename_album_triggers_callback(self, album_manager):
        """Test that renaming an album triggers the albums changed callback."""
        albums = album_manager.load_albums()
        album = albums[0]

        callback_called = False

        def callback(albums):
            nonlocal callback_called
            callback_called = True

        album_manager.set_albums_changed_callback(callback)

        # Rename album
        album_manager.rename_album(album, "2024-01-15_Callback_Rename_Test")

        # Verify callback was called
        assert callback_called


# ==================== File Validator Tests ====================

class TestFileValidator:
    """Tests for file validator utility functions."""

    def test_validate_valid_album_names(self):
        """Test validation of valid album names."""
        valid_names = [
            "2024-01-15_Album",
            "Simple Album",
            "Trip to Zürich",
            "Photos-2024",
            "Album_123"
        ]

        for name in valid_names:
            is_valid, error = FileValidator.validate_album_name(name)
            assert is_valid is True
            assert error is None

    def test_validate_invalid_album_names(self):
        """Test validation of invalid album names."""
        invalid_names = [
            ("", "empty"),
            ("   ", "empty"),
            ("Album/Slash", "invalid characters"),
            ("Album\\Backslash", "invalid characters"),
            ("Album:Colon", "invalid characters"),
            ("Album*Asterisk", "invalid characters"),
            ("CON", "reserved"),
            ("PRN", "reserved"),
            ("...", "dots")
        ]

        for name, reason in invalid_names:
            is_valid, error = FileValidator.validate_album_name(name)
            assert is_valid is False
            assert error is not None

    def test_check_album_name_availability(self, temp_photo_dir):
        """Test checking album name availability."""
        # Existing album
        existing = "2024-01-15_Test_Album_1"
        assert FileValidator.is_album_name_available(temp_photo_dir, existing) is False

        # Non-existing album
        new_name = "2024-05-20_New_Album"
        assert FileValidator.is_album_name_available(temp_photo_dir, new_name) is True

    def test_validate_and_check_availability(self, temp_photo_dir):
        """Test combined validation and availability check."""
        # Valid and available
        is_valid, error = FileValidator.validate_and_check_availability(
            temp_photo_dir,
            "2024-05-20_New_Album"
        )
        assert is_valid is True
        assert error is None

        # Valid but not available
        is_valid, error = FileValidator.validate_and_check_availability(
            temp_photo_dir,
            "2024-01-15_Test_Album_1"
        )
        assert is_valid is False
        assert "already exists" in error

        # Invalid name
        is_valid, error = FileValidator.validate_and_check_availability(
            temp_photo_dir,
            "Album/Invalid"
        )
        assert is_valid is False
        assert error is not None

    def test_sanitize_album_name(self):
        """Test album name sanitization."""
        # Replace invalid characters
        assert FileValidator.sanitize_album_name("Album/With*Invalid") == "Album_With_Invalid"

        # Handle reserved names
        assert "album" in FileValidator.sanitize_album_name("CON").lower()

        # Handle empty names
        assert FileValidator.sanitize_album_name("") == "Untitled"
        assert FileValidator.sanitize_album_name("   ") == "Untitled"
