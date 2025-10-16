"""Tests for PhotoProcessor service - RAW-JPEG pairing and preview extraction.

Critical tests for:
- RAW-JPEG pair detection logic (complex algorithm)
- Embedded RAW preview extraction (performance-critical)
"""

import io
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
from PIL import Image

from src.models.photo import Photo, PhotoPair
from src.services.photo_processor import PhotoProcessor


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary cache directory."""
    cache_dir = tmp_path / "thumbnails"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def photo_processor(temp_cache_dir):
    """Create PhotoProcessor instance with temp cache."""
    return PhotoProcessor(temp_cache_dir)


@pytest.fixture
def sample_photos(tmp_path):
    """Create sample photo files for testing."""
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()

    # Create sample JPEG files
    for name in ["IMG_001.jpg", "IMG_002.jpg", "IMG_003.jpg"]:
        photo_path = photos_dir / name
        # Create a simple 100x100 red image
        img = Image.new("RGB", (100, 100), color="red")
        img.save(photo_path, "JPEG")

    # Create matching RAW file (just a dummy file)
    (photos_dir / "IMG_001.cr3").write_text("fake RAW data")
    (photos_dir / "IMG_002.nef").write_text("fake RAW data")

    # Create standalone RAW file
    (photos_dir / "IMG_999.cr3").write_text("fake RAW standalone")

    return photos_dir


class TestRawJpegPairDetection:
    """Test RAW-JPEG pair detection logic."""

    def test_detect_pairs_with_matching_raw_jpeg(self):
        """Test detection of matching RAW-JPEG pairs."""
        photos = [
            Photo(path=Path("/photos/IMG_001.jpg")),
            Photo(path=Path("/photos/IMG_001.cr3")),
            Photo(path=Path("/photos/IMG_002.jpg")),
        ]

        pairs = PhotoPair.detect_pairs(photos)

        # Should detect one pair (IMG_001) and one standalone JPEG
        assert len(pairs) == 2

        # Find the pair with RAW
        paired = [p for p in pairs if p.has_raw]
        assert len(paired) == 1
        assert paired[0].base_name == "IMG_001"
        assert paired[0].jpeg_path == Path("/photos/IMG_001.jpg")
        assert paired[0].raw_path == Path("/photos/IMG_001.cr3")

        # Find standalone JPEG
        standalone = [p for p in pairs if not p.has_raw]
        assert len(standalone) == 1
        assert standalone[0].base_name == "IMG_002"

    def test_detect_pairs_with_multiple_raw_formats(self):
        """Test detection with different RAW formats (CR3, NEF, ARW)."""
        photos = [
            Photo(path=Path("/photos/IMG_001.jpg")),
            Photo(path=Path("/photos/IMG_001.cr3")),
            Photo(path=Path("/photos/IMG_002.jpg")),
            Photo(path=Path("/photos/IMG_002.nef")),
            Photo(path=Path("/photos/IMG_003.jpg")),
            Photo(path=Path("/photos/IMG_003.arw")),
        ]

        pairs = PhotoPair.detect_pairs(photos)

        assert len(pairs) == 3
        assert all(p.has_raw for p in pairs)

        # Verify each format is detected
        raw_formats = {p.raw_path.suffix for p in pairs}
        assert raw_formats == {".cr3", ".nef", ".arw"}

    def test_detect_pairs_jpeg_only(self):
        """Test with only JPEG files (no RAW)."""
        photos = [
            Photo(path=Path("/photos/IMG_001.jpg")),
            Photo(path=Path("/photos/IMG_002.jpg")),
            Photo(path=Path("/photos/IMG_003.jpg")),
        ]

        pairs = PhotoPair.detect_pairs(photos)

        assert len(pairs) == 3
        assert all(not p.has_raw for p in pairs)
        assert all(p.display_path.suffix == ".jpg" for p in pairs)

    def test_detect_pairs_raw_only(self):
        """Test with only RAW files (no matching JPEG)."""
        photos = [
            Photo(path=Path("/photos/IMG_001.cr3")),
            Photo(path=Path("/photos/IMG_002.nef")),
        ]

        pairs = PhotoPair.detect_pairs(photos)

        # Standalone RAW files without JPEG should not create pairs
        assert len(pairs) == 0

    def test_detect_pairs_mixed_naming(self):
        """Test detection with different naming conventions."""
        photos = [
            Photo(path=Path("/photos/DSC_0123.jpg")),
            Photo(path=Path("/photos/DSC_0123.nef")),
            Photo(path=Path("/photos/IMG_5678.JPG")),  # Uppercase extension
            Photo(path=Path("/photos/IMG_5678.CR3")),  # Uppercase extension
            Photo(path=Path("/photos/photo-001.jpg")),
            Photo(path=Path("/photos/photo-001.arw")),
        ]

        pairs = PhotoPair.detect_pairs(photos)

        assert len(pairs) == 3
        assert all(p.has_raw for p in pairs)

        base_names = {p.base_name for p in pairs}
        assert base_names == {"DSC_0123", "IMG_5678", "photo-001"}

    def test_detect_pairs_deduplication(self):
        """Test that pairs properly deduplicate RAW-JPEG combos."""
        photos = [
            Photo(path=Path("/photos/IMG_001.jpg")),
            Photo(path=Path("/photos/IMG_001.cr3")),
            Photo(path=Path("/photos/IMG_002.jpg")),
        ]

        pairs = PhotoPair.detect_pairs(photos)

        # 3 photos should become 2 pairs (IMG_001 paired, IMG_002 standalone)
        assert len(pairs) == 2

        # Verify IMG_001 is paired
        img_001_pair = next(p for p in pairs if p.base_name == "IMG_001")
        assert img_001_pair.has_raw
        assert len(img_001_pair.get_all_paths()) == 2

    def test_detect_pairs_empty_list(self):
        """Test with empty photo list."""
        pairs = PhotoPair.detect_pairs([])
        assert len(pairs) == 0

    def test_photo_pair_display_path_preference(self):
        """Test that display_path always prefers JPEG."""
        pair = PhotoPair(
            base_name="IMG_001",
            jpeg_path=Path("/photos/IMG_001.jpg"),
            raw_path=Path("/photos/IMG_001.cr3")
        )

        assert pair.display_path == Path("/photos/IMG_001.jpg")
        assert pair.display_path.suffix == ".jpg"

    def test_photo_pair_get_all_paths(self):
        """Test getting all file paths from a pair."""
        # Pair with RAW
        pair_with_raw = PhotoPair(
            base_name="IMG_001",
            jpeg_path=Path("/photos/IMG_001.jpg"),
            raw_path=Path("/photos/IMG_001.cr3")
        )
        assert len(pair_with_raw.get_all_paths()) == 2
        assert Path("/photos/IMG_001.jpg") in pair_with_raw.get_all_paths()
        assert Path("/photos/IMG_001.cr3") in pair_with_raw.get_all_paths()

        # JPEG only
        pair_jpeg_only = PhotoPair(
            base_name="IMG_002",
            jpeg_path=Path("/photos/IMG_002.jpg")
        )
        assert len(pair_jpeg_only.get_all_paths()) == 1
        assert pair_jpeg_only.get_all_paths()[0] == Path("/photos/IMG_002.jpg")


class TestRawPreviewExtraction:
    """Test embedded RAW preview extraction."""

    @patch('src.services.photo_processor.rawpy')
    def test_extract_raw_preview_with_embedded_jpeg(self, mock_rawpy, photo_processor):
        """Test extraction of embedded JPEG preview from RAW file."""
        # Create a fake JPEG preview
        fake_jpeg = io.BytesIO()
        fake_img = Image.new("RGB", (200, 200), color="blue")
        fake_img.save(fake_jpeg, "JPEG")
        fake_jpeg.seek(0)

        # Mock rawpy to return embedded preview
        mock_raw = MagicMock()
        mock_thumb = MagicMock()
        mock_thumb.format = MagicMock()
        mock_thumb.format.__eq__ = lambda self, other: True  # Mock JPEG format check
        mock_thumb.data = fake_jpeg.getvalue()
        mock_raw.extract_thumb.return_value = mock_thumb
        mock_raw.__enter__ = Mock(return_value=mock_raw)
        mock_raw.__exit__ = Mock(return_value=False)
        mock_rawpy.imread.return_value = mock_raw
        mock_rawpy.ThumbFormat.JPEG = MagicMock()

        # Extract preview
        result = photo_processor._extract_raw_preview(Path("/photos/test.cr3"))

        assert result is not None
        assert isinstance(result, Image.Image)
        mock_rawpy.imread.assert_called_once()

    @patch('src.services.photo_processor.rawpy')
    def test_extract_raw_preview_fallback_to_decode(self, mock_rawpy, photo_processor):
        """Test fallback to full RAW decode when preview extraction fails."""
        import numpy as np

        # Mock rawpy with no embedded preview
        mock_raw = MagicMock()
        mock_raw.extract_thumb.side_effect = Exception("No preview")

        # Mock postprocess to return fake RGB array
        fake_rgb = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_raw.postprocess.return_value = fake_rgb

        mock_raw.__enter__ = Mock(return_value=mock_raw)
        mock_raw.__exit__ = Mock(return_value=False)
        mock_rawpy.imread.return_value = mock_raw

        # Extract preview (should fall back to decode)
        result = photo_processor._extract_raw_preview(Path("/photos/test.cr3"))

        assert result is not None
        assert isinstance(result, Image.Image)
        mock_raw.postprocess.assert_called_once()

    def test_extract_raw_preview_without_rawpy(self, photo_processor):
        """Test that RAW extraction fails gracefully without rawpy."""
        with patch('src.services.photo_processor.rawpy', None):
            with pytest.raises(ImportError, match="rawpy is required"):
                photo_processor._extract_raw_preview(Path("/photos/test.cr3"))

    @patch('src.services.photo_processor.rawpy')
    def test_load_image_for_thumbnail_raw_format(self, mock_rawpy, photo_processor):
        """Test that _load_image_for_thumbnail calls RAW extraction for RAW files."""
        # Setup mock
        fake_jpeg = io.BytesIO()
        fake_img = Image.new("RGB", (100, 100), color="green")
        fake_img.save(fake_jpeg, "JPEG")
        fake_jpeg.seek(0)

        mock_raw = MagicMock()
        mock_thumb = MagicMock()
        mock_thumb.format = MagicMock()
        mock_thumb.format.__eq__ = lambda self, other: True
        mock_thumb.data = fake_jpeg.getvalue()
        mock_raw.extract_thumb.return_value = mock_thumb
        mock_raw.__enter__ = Mock(return_value=mock_raw)
        mock_raw.__exit__ = Mock(return_value=False)
        mock_rawpy.imread.return_value = mock_raw
        mock_rawpy.ThumbFormat.JPEG = MagicMock()

        # Test various RAW formats
        for ext in ['.cr3', '.cr2', '.nef', '.arw', '.dng', '.raw']:
            result = photo_processor._load_image_for_thumbnail(Path(f"/photos/test{ext}"))
            assert isinstance(result, Image.Image)

    def test_load_image_for_thumbnail_standard_format(self, photo_processor, sample_photos):
        """Test that _load_image_for_thumbnail uses PIL for standard formats."""
        jpeg_path = sample_photos / "IMG_001.jpg"
        result = photo_processor._load_image_for_thumbnail(jpeg_path)

        assert isinstance(result, Image.Image)
        assert result.size == (100, 100)


class TestPhotoProcessorIntegration:
    """Integration tests for PhotoProcessor with pair detection."""

    def test_detect_raw_jpeg_pairs_delegates_to_model(self, photo_processor):
        """Test that detect_raw_jpeg_pairs delegates to PhotoPair.detect_pairs."""
        photos = [
            Photo(path=Path("/photos/IMG_001.jpg")),
            Photo(path=Path("/photos/IMG_001.cr3")),
        ]

        pairs = photo_processor.detect_raw_jpeg_pairs(photos)

        assert len(pairs) == 1
        assert pairs[0].has_raw
        assert pairs[0].base_name == "IMG_001"

    def test_generate_thumbnail_for_jpeg(self, photo_processor, sample_photos):
        """Test thumbnail generation for JPEG file."""
        jpeg_path = sample_photos / "IMG_001.jpg"

        thumbnail_path = photo_processor.generate_thumbnail(jpeg_path, size=(50, 50))

        assert thumbnail_path is not None
        assert thumbnail_path.exists()

        # Verify thumbnail is correct size
        with Image.open(thumbnail_path) as thumb:
            assert thumb.size[0] <= 50
            assert thumb.size[1] <= 50

    @patch('src.services.photo_processor.rawpy')
    def test_generate_thumbnail_for_raw(self, mock_rawpy, photo_processor, tmp_path):
        """Test thumbnail generation for RAW file."""
        # Create mock RAW file
        raw_path = tmp_path / "test.cr3"
        raw_path.write_text("fake raw")

        # Setup mock
        fake_jpeg = io.BytesIO()
        fake_img = Image.new("RGB", (400, 300), color="red")
        fake_img.save(fake_jpeg, "JPEG")
        fake_jpeg.seek(0)

        mock_raw = MagicMock()
        mock_thumb = MagicMock()
        mock_thumb.format = MagicMock()
        mock_thumb.format.__eq__ = lambda self, other: True
        mock_thumb.data = fake_jpeg.getvalue()
        mock_raw.extract_thumb.return_value = mock_thumb
        mock_raw.__enter__ = Mock(return_value=mock_raw)
        mock_raw.__exit__ = Mock(return_value=False)
        mock_rawpy.imread.return_value = mock_raw
        mock_rawpy.ThumbFormat.JPEG = MagicMock()

        thumbnail_path = photo_processor.generate_thumbnail(raw_path, size=(100, 100))

        assert thumbnail_path is not None
        assert thumbnail_path.exists()

    def test_thumbnail_caching(self, photo_processor, sample_photos):
        """Test that thumbnails are cached and reused."""
        jpeg_path = sample_photos / "IMG_001.jpg"

        # Generate thumbnail first time
        thumb1 = photo_processor.generate_thumbnail(jpeg_path, size=(50, 50))
        assert thumb1 is not None

        # Generate again - should return cached version
        thumb2 = photo_processor.generate_thumbnail(jpeg_path, size=(50, 50))
        assert thumb2 == thumb1

    def test_corrupted_image_handling(self, photo_processor, tmp_path):
        """Test handling of corrupted image files."""
        # Create a fake "corrupted" image
        corrupted = tmp_path / "corrupted.jpg"
        corrupted.write_text("not a real image")

        # Should return None instead of crashing
        result = photo_processor.generate_thumbnail(corrupted)
        assert result is None

        # is_corrupted should detect it
        assert photo_processor.is_corrupted(corrupted)


class TestPhotoModel:
    """Test Photo model properties."""

    def test_photo_is_raw_property(self):
        """Test is_raw property for different formats."""
        raw_formats = [".cr3", ".cr2", ".nef", ".arw", ".dng", ".raw"]
        for ext in raw_formats:
            photo = Photo(path=Path(f"/photos/test{ext}"))
            assert photo.is_raw, f"Failed for {ext}"

        standard_formats = [".jpg", ".jpeg", ".png", ".heic"]
        for ext in standard_formats:
            photo = Photo(path=Path(f"/photos/test{ext}"))
            assert not photo.is_raw, f"Failed for {ext}"

    def test_photo_base_name_property(self):
        """Test base_name extraction."""
        photo = Photo(path=Path("/photos/IMG_12345.jpg"))
        assert photo.base_name == "IMG_12345"

        photo2 = Photo(path=Path("/photos/DSC-0001.cr3"))
        assert photo2.base_name == "DSC-0001"
