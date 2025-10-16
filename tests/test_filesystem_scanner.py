"""Tests for FilesystemScanner service.

These tests verify critical functionality:
- Album discovery and scanning
- Date parsing from folder names
- Flat hierarchy enforcement
- Photo counting
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from datetime import date
import tempfile
import shutil

from src.services.filesystem_scanner import FilesystemScanner
from src.models.album import Album


class TestAlbumDiscovery:
    """Test album discovery and scanning functionality."""

    @pytest.fixture
    def temp_photo_dir(self):
        """Create a temporary photo directory structure."""
        temp_dir = Path(tempfile.mkdtemp())

        # Create various album directories
        (temp_dir / "2024-01-15_Vacation").mkdir()
        (temp_dir / "2023-12-25_Christmas").mkdir()
        (temp_dir / "2024-03-10").mkdir()
        (temp_dir / "random_album").mkdir()
        (temp_dir / ".hidden_album").mkdir()  # Should be ignored

        # Create a nested directory (should be ignored - flat hierarchy)
        (temp_dir / "2024-01-15_Vacation" / "nested").mkdir()

        # Create some photos in albums
        (temp_dir / "2024-01-15_Vacation" / "IMG_001.jpg").touch()
        (temp_dir / "2024-01-15_Vacation" / "IMG_002.jpg").touch()
        (temp_dir / "2024-01-15_Vacation" / "IMG_003.cr3").touch()  # RAW

        (temp_dir / "2023-12-25_Christmas" / "photo1.jpg").touch()

        (temp_dir / "2024-03-10" / "pic.png").touch()

        # Empty album
        (temp_dir / "random_album")  # No photos

        # Create a regular file in root (should be ignored)
        (temp_dir / "readme.txt").touch()

        yield temp_dir

        # Cleanup
        shutil.rmtree(temp_dir)

    def test_scanner_initialization_valid_directory(self, temp_photo_dir):
        """Test scanner initializes with valid directory."""
        scanner = FilesystemScanner(temp_photo_dir)
        assert scanner.root_dir == temp_photo_dir

    def test_scanner_initialization_invalid_directory(self):
        """Test scanner raises error with invalid directory."""
        with pytest.raises(ValueError, match="does not exist"):
            FilesystemScanner(Path("/nonexistent/directory"))

    def test_scanner_initialization_file_instead_of_directory(self, temp_photo_dir):
        """Test scanner raises error when given a file path."""
        file_path = temp_photo_dir / "readme.txt"
        with pytest.raises(ValueError, match="not a directory"):
            FilesystemScanner(file_path)

    def test_scan_albums_discovers_all_valid_albums(self, temp_photo_dir):
        """Test scan_albums discovers all valid album directories."""
        scanner = FilesystemScanner(temp_photo_dir)
        albums = scanner.scan_albums()

        # Should find 4 albums (excludes hidden, nested, and files)
        assert len(albums) == 4

        # Check album names
        album_names = {album.name for album in albums}
        assert "2024-01-15_Vacation" in album_names
        assert "2023-12-25_Christmas" in album_names
        assert "2024-03-10" in album_names
        assert "random_album" in album_names

        # Hidden album should not be included
        assert ".hidden_album" not in album_names

    def test_scan_albums_ignores_hidden_directories(self, temp_photo_dir):
        """Test that hidden directories (starting with .) are ignored."""
        scanner = FilesystemScanner(temp_photo_dir)
        albums = scanner.scan_albums()

        hidden_albums = [a for a in albums if a.name.startswith('.')]
        assert len(hidden_albums) == 0

    def test_scan_albums_enforces_flat_hierarchy(self, temp_photo_dir):
        """Test that nested subdirectories are not treated as albums."""
        scanner = FilesystemScanner(temp_photo_dir)
        albums = scanner.scan_albums()

        # "nested" directory inside Vacation should not appear
        nested_albums = [a for a in albums if a.name == "nested"]
        assert len(nested_albums) == 0

    def test_scan_albums_counts_photos_correctly(self, temp_photo_dir):
        """Test that photo counts are accurate."""
        scanner = FilesystemScanner(temp_photo_dir)
        albums = scanner.scan_albums()

        # Find specific albums and check counts
        vacation_album = next(a for a in albums if a.name == "2024-01-15_Vacation")
        assert vacation_album.photo_count == 3  # 2 JPG + 1 CR3

        christmas_album = next(a for a in albums if a.name == "2023-12-25_Christmas")
        assert christmas_album.photo_count == 1

        empty_album = next(a for a in albums if a.name == "random_album")
        assert empty_album.photo_count == 0

    def test_scan_photos_in_album(self, temp_photo_dir):
        """Test scanning photos within an album."""
        scanner = FilesystemScanner(temp_photo_dir)
        album_path = temp_photo_dir / "2024-01-15_Vacation"

        photos = scanner.scan_photos_in_album(album_path)

        assert len(photos) == 3
        photo_names = {photo.filename for photo in photos}
        assert "IMG_001.jpg" in photo_names
        assert "IMG_002.jpg" in photo_names
        assert "IMG_003.cr3" in photo_names

    def test_scan_photos_in_nonexistent_album(self):
        """Test scanning photos in nonexistent directory returns empty list."""
        scanner = FilesystemScanner(Path.cwd())
        photos = scanner.scan_photos_in_album(Path("/nonexistent/album"))

        assert len(photos) == 0

    def test_find_album_by_path(self, temp_photo_dir):
        """Test finding an album by its path."""
        scanner = FilesystemScanner(temp_photo_dir)
        album_path = temp_photo_dir / "2024-01-15_Vacation"

        album = scanner.find_album_by_path(album_path)

        assert album is not None
        assert album.name == "2024-01-15_Vacation"
        assert album.photo_count == 3

    def test_find_album_by_path_nonexistent(self, temp_photo_dir):
        """Test finding nonexistent album returns None."""
        scanner = FilesystemScanner(temp_photo_dir)
        album = scanner.find_album_by_path(temp_photo_dir / "nonexistent")

        assert album is None

    def test_find_album_by_path_nested_directory(self, temp_photo_dir):
        """Test finding nested directory returns None (flat hierarchy)."""
        scanner = FilesystemScanner(temp_photo_dir)
        nested_path = temp_photo_dir / "2024-01-15_Vacation" / "nested"

        album = scanner.find_album_by_path(nested_path)

        assert album is None  # Not a valid album (not direct child of root)

    def test_is_valid_album_directory(self, temp_photo_dir):
        """Test album directory validation."""
        scanner = FilesystemScanner(temp_photo_dir)

        # Valid album
        valid_path = temp_photo_dir / "2024-01-15_Vacation"
        assert scanner.is_valid_album_directory(valid_path) is True

        # Hidden directory
        hidden_path = temp_photo_dir / ".hidden_album"
        assert scanner.is_valid_album_directory(hidden_path) is False

        # Nested directory
        nested_path = temp_photo_dir / "2024-01-15_Vacation" / "nested"
        assert scanner.is_valid_album_directory(nested_path) is False

        # File (not directory)
        file_path = temp_photo_dir / "readme.txt"
        assert scanner.is_valid_album_directory(file_path) is False

    def test_get_album_count(self, temp_photo_dir):
        """Test getting album count."""
        scanner = FilesystemScanner(temp_photo_dir)
        count = scanner.get_album_count()

        assert count == 4  # 4 valid albums

    def test_refresh_album_updates_metadata(self, temp_photo_dir):
        """Test refreshing album updates its metadata."""
        scanner = FilesystemScanner(temp_photo_dir)
        album_path = temp_photo_dir / "2024-01-15_Vacation"

        # Create initial album
        album = Album(path=album_path, photo_count=0)

        # Refresh from filesystem
        refreshed_album = scanner.refresh_album(album)

        assert refreshed_album.photo_count == 3
        assert refreshed_album.name == "2024-01-15_Vacation"
        assert refreshed_album.date == date(2024, 1, 15)

    def test_refresh_album_nonexistent_raises_error(self):
        """Test refreshing nonexistent album raises error."""
        scanner = FilesystemScanner(Path.cwd())
        album = Album(path=Path("/nonexistent/album"))

        with pytest.raises(FileNotFoundError):
            scanner.refresh_album(album)

    def test_verify_album_exists(self, temp_photo_dir):
        """Test verifying album existence."""
        scanner = FilesystemScanner(temp_photo_dir)

        # Existing album
        existing_path = temp_photo_dir / "2024-01-15_Vacation"
        assert scanner.verify_album_exists(existing_path) is True

        # Nonexistent album
        nonexistent_path = temp_photo_dir / "nonexistent"
        assert scanner.verify_album_exists(nonexistent_path) is False


class TestDateParsing:
    """Test date parsing from folder names."""

    def test_parse_date_basic_format(self):
        """Test parsing basic YYYY-MM-DD format."""
        result = Album.parse_date_from_name("2024-01-15")
        assert result == date(2024, 1, 15)

    def test_parse_date_with_description(self):
        """Test parsing date with description suffix."""
        result = Album.parse_date_from_name("2024-01-15_Vacation")
        assert result == date(2024, 1, 15)

    def test_parse_date_with_multiple_underscores(self):
        """Test parsing date with multiple description parts."""
        result = Album.parse_date_from_name("2024-01-15_Paris_City_Trip")
        assert result == date(2024, 1, 15)

    def test_parse_date_no_date_present(self):
        """Test parsing folder name without date returns None."""
        result = Album.parse_date_from_name("random_album")
        assert result is None

    def test_parse_date_invalid_date_values(self):
        """Test parsing invalid date values returns None."""
        # Invalid month
        result = Album.parse_date_from_name("2024-13-15")
        assert result is None

        # Invalid day
        result = Album.parse_date_from_name("2024-02-30")
        assert result is None

    def test_parse_date_incomplete_format(self):
        """Test parsing incomplete date format returns None."""
        result = Album.parse_date_from_name("2024-01")
        assert result is None

    def test_parse_date_wrong_separator(self):
        """Test parsing date with wrong separator returns None."""
        result = Album.parse_date_from_name("2024/01/15")
        assert result is None

    def test_parse_date_embedded_in_name(self):
        """Test parsing date not at start of name returns None."""
        result = Album.parse_date_from_name("Vacation_2024-01-15")
        assert result is None

    def test_parse_date_various_years(self):
        """Test parsing dates across different years."""
        assert Album.parse_date_from_name("2020-01-01") == date(2020, 1, 1)
        assert Album.parse_date_from_name("2023-12-31") == date(2023, 12, 31)
        assert Album.parse_date_from_name("2025-06-15") == date(2025, 6, 15)

    def test_parse_date_leap_year(self):
        """Test parsing leap year dates."""
        # Valid leap year date
        result = Album.parse_date_from_name("2024-02-29")
        assert result == date(2024, 2, 29)

        # Invalid leap year date
        result = Album.parse_date_from_name("2023-02-29")
        assert result is None

    def test_album_date_set_on_initialization(self, tmp_path):
        """Test album automatically parses date on initialization."""
        album_path = tmp_path / "2024-01-15_Vacation"
        album_path.mkdir()

        album = Album(path=album_path)

        assert album.date == date(2024, 1, 15)
        assert album.name == "2024-01-15_Vacation"

    def test_album_date_string_property(self, tmp_path):
        """Test album date_string property formatting."""
        album_path = tmp_path / "2024-01-15_Vacation"
        album_path.mkdir()

        album = Album(path=album_path)
        assert album.date_string == "2024-01-15"

        # Album without date
        album_no_date = Album(path=tmp_path / "random")
        assert album_no_date.date_string == "Unknown Date"
