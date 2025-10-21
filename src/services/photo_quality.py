"""
Photo Quality Ranking Service

Implements EXIF-based quality scoring for photo highlighting and selection.
Uses technical metadata to assess photo quality without ML/AI models.

Date: 2025-10-20
Feature: Library View (002-library-view)
"""

from datetime import timedelta
from pathlib import Path
from typing import Optional


class PhotoQualityRanker:
    """
    Service for photo quality assessment using EXIF metadata.

    Implements IPhotoQualityRanker interface from contracts/library_view_api.py.

    Quality scoring based on:
    - ISO sensitivity (40%): Lower ISO = less noise
    - Camera shake risk (30%): Reciprocal rule compliance
    - Aperture (15%): Mid-range f/5.6-f/11 optimal
    - Exposure compensation (10%): Small adjustments preferred
    - Flash usage (5%): Natural light preferred
    """

    def __init__(self):
        """Initialize quality ranker with default settings."""
        # Quality score weights (must sum to 1.0)
        self.weight_iso = 0.40
        self.weight_shake = 0.30
        self.weight_aperture = 0.15
        self.weight_exposure = 0.10
        self.weight_flash = 0.05

    def calculate_score(self, exif_data: dict) -> float:
        """
        Calculate quality score from EXIF metadata.

        Args:
            exif_data: EXIF dictionary from exifread

        Returns:
            Quality score 0-100 (higher = better quality)
            50.0 if EXIF data is missing/incomplete (neutral score)

        Performance: O(1) - simple weighted calculation
        """
        if not exif_data:
            return 50.0  # Neutral score for missing EXIF

        # Extract EXIF fields (handle missing data gracefully)
        iso = self._extract_iso(exif_data)
        shutter_speed = self._extract_shutter_speed(exif_data)
        focal_length = self._extract_focal_length(exif_data)
        aperture = self._extract_aperture(exif_data)
        exposure_comp = self._extract_exposure_comp(exif_data)
        flash_fired = self._extract_flash(exif_data)

        # Calculate component scores (0-100 each)
        iso_score = self._score_iso(iso)
        shake_score = self._score_camera_shake(shutter_speed, focal_length)
        aperture_score = self._score_aperture(aperture)
        exposure_score = self._score_exposure_comp(exposure_comp)
        flash_score = self._score_flash(flash_fired)

        # Weighted combination
        weighted = (
            iso_score * self.weight_iso +
            shake_score * self.weight_shake +
            aperture_score * self.weight_aperture +
            exposure_score * self.weight_exposure +
            flash_score * self.weight_flash
        )

        # Clamp to valid range
        return max(0.0, min(100.0, weighted))

    def select_best_shots(self, items: list, max_count: int) -> list:
        """
        Select best shots from a collection based on quality scores.

        Args:
            items: List of LibraryItem objects
            max_count: Maximum number of best shots to return

        Returns:
            Top-scoring items (sorted by quality descending)

        Performance: O(n*log(n)) for sorting
        """
        # Filter photos only (no videos)
        photos = [item for item in items if hasattr(item, 'media_type') and
                  str(item.media_type).lower().endswith('photo')]

        # Filter items with quality scores
        scored = [photo for photo in photos if photo.quality_score is not None]

        if not scored:
            return []

        # Sort by quality score (descending)
        scored.sort(key=lambda p: p.quality_score, reverse=True)

        # Return top N
        return scored[:max_count]

    def select_highlights_with_variety(
        self,
        items: list,
        target_count: int,
        time_buckets: int = 12
    ) -> list:
        """
        Select highlights balancing quality with temporal variety.

        Used for Years view to ensure highlights spread across the year,
        not just clustered in high-quality events.

        Args:
            items: List of LibraryItem objects (must be sorted chronologically)
            target_count: Desired number of highlights (20-50)
            time_buckets: Number of temporal buckets (e.g., 12 for months)

        Returns:
            Selected highlights balancing quality and temporal distribution

        Performance: O(n*log(n)) for sorting + partitioning

        Algorithm:
        1. Divide items into time buckets (e.g., months)
        2. Select top-quality photos from each bucket proportionally
        3. Ensure minimum representation from each bucket
        """
        if not items or target_count <= 0:
            return []

        # Filter photos only
        photos = [item for item in items if hasattr(item, 'media_type') and
                  str(item.media_type).lower().endswith('photo')]

        # Filter scored photos
        scored = [p for p in photos if p.quality_score is not None]

        if not scored:
            return []

        # Divide into time buckets
        buckets = self._partition_by_time(scored, time_buckets)

        # Calculate photos per bucket (minimum 2 per bucket)
        photos_per_bucket = max(2, target_count // len(buckets))

        highlights = []

        # Select top photos from each bucket
        for bucket in buckets:
            # Sort bucket by quality
            bucket.sort(key=lambda p: p.quality_score, reverse=True)

            # Take proportional share
            count = min(photos_per_bucket, len(bucket))
            highlights.extend(bucket[:count])

        # Sort all highlights by quality and cap at target
        highlights.sort(key=lambda p: p.quality_score, reverse=True)

        # Ensure within range [20, 50]
        final_count = min(50, max(20, len(highlights)))
        return highlights[:final_count]

    # ========================================================================
    # EXIF Extraction Helpers
    # ========================================================================

    def _extract_iso(self, exif_data: dict) -> Optional[int]:
        """Extract ISO sensitivity from EXIF data."""
        try:
            # Try standard EXIF tag
            if 'EXIF ISOSpeedRatings' in exif_data:
                return int(str(exif_data['EXIF ISOSpeedRatings']))
            # Try alternative tag
            if 'ISOSpeedRatings' in exif_data:
                return int(str(exif_data['ISOSpeedRatings']))
        except (ValueError, AttributeError):
            pass
        return None

    def _extract_shutter_speed(self, exif_data: dict) -> Optional[float]:
        """Extract shutter speed in seconds from EXIF data."""
        try:
            if 'EXIF ExposureTime' in exif_data:
                value = exif_data['EXIF ExposureTime']
                # Handle fraction format "1/500"
                if hasattr(value, 'num') and hasattr(value, 'den'):
                    return value.num / value.den
                # Handle string format
                val_str = str(value)
                if '/' in val_str:
                    num, den = val_str.split('/')
                    return float(num) / float(den)
                return float(val_str)
        except (ValueError, AttributeError, ZeroDivisionError):
            pass
        return None

    def _extract_focal_length(self, exif_data: dict) -> Optional[int]:
        """Extract focal length in mm from EXIF data."""
        try:
            if 'EXIF FocalLength' in exif_data:
                value = exif_data['EXIF FocalLength']
                # Handle fraction format
                if hasattr(value, 'num') and hasattr(value, 'den'):
                    return int(value.num / value.den)
                # Handle string format
                val_str = str(value)
                if '/' in val_str:
                    num, den = val_str.split('/')
                    return int(float(num) / float(den))
                return int(float(val_str))
        except (ValueError, AttributeError, ZeroDivisionError):
            pass
        return None

    def _extract_aperture(self, exif_data: dict) -> Optional[float]:
        """Extract aperture (f-stop) from EXIF data."""
        try:
            if 'EXIF FNumber' in exif_data:
                value = exif_data['EXIF FNumber']
                # Handle fraction format
                if hasattr(value, 'num') and hasattr(value, 'den'):
                    return value.num / value.den
                # Handle string format
                val_str = str(value)
                if '/' in val_str:
                    num, den = val_str.split('/')
                    return float(num) / float(den)
                return float(val_str)
        except (ValueError, AttributeError, ZeroDivisionError):
            pass
        return None

    def _extract_exposure_comp(self, exif_data: dict) -> Optional[float]:
        """Extract exposure compensation in stops from EXIF data."""
        try:
            if 'EXIF ExposureBiasValue' in exif_data:
                value = exif_data['EXIF ExposureBiasValue']
                # Handle fraction format
                if hasattr(value, 'num') and hasattr(value, 'den'):
                    return value.num / value.den
                # Handle string format
                val_str = str(value)
                if '/' in val_str:
                    num, den = val_str.split('/')
                    return float(num) / float(den)
                return float(val_str)
        except (ValueError, AttributeError, ZeroDivisionError):
            pass
        return None

    def _extract_flash(self, exif_data: dict) -> Optional[bool]:
        """Extract flash fired status from EXIF data."""
        try:
            if 'EXIF Flash' in exif_data:
                value = int(str(exif_data['EXIF Flash']))
                # Flash fired if bit 0 is set
                return (value & 0x01) == 1
        except (ValueError, AttributeError):
            pass
        return None

    # ========================================================================
    # Quality Scoring Helpers
    # ========================================================================

    def _score_iso(self, iso: Optional[int]) -> float:
        """
        Score ISO sensitivity (0-100).

        Lower ISO = better quality (less noise)

        Scoring:
        - ISO 100-400: 100 points (excellent)
        - ISO 400-800: 80 points (good)
        - ISO 800-1600: 60 points (acceptable)
        - ISO 1600-3200: 40 points (noisy)
        - ISO 3200+: 20 points (very noisy)
        - Missing: 50 points (neutral)

        Args:
            iso: ISO sensitivity value

        Returns:
            Score 0-100
        """
        if iso is None:
            return 50.0  # Neutral for missing data

        if iso <= 400:
            return 100.0
        elif iso <= 800:
            return 80.0
        elif iso <= 1600:
            return 60.0
        elif iso <= 3200:
            return 40.0
        else:
            return 20.0

    def _score_camera_shake(
        self,
        shutter_speed: Optional[float],
        focal_length: Optional[int]
    ) -> float:
        """
        Score camera shake risk using reciprocal rule (0-100).

        Reciprocal rule: Minimum shutter speed = 1 / (focal_length * crop_factor)
        For full-frame: shutter_speed should be >= 1 / focal_length

        Scoring:
        - 2x faster than rule: 100 points (excellent)
        - 1x rule speed: 80 points (good)
        - 0.5x rule speed: 60 points (risky)
        - Slower than rule: 40 points (likely blurry)
        - Missing data: 50 points (neutral)

        Args:
            shutter_speed: Shutter speed in seconds
            focal_length: Focal length in mm

        Returns:
            Score 0-100
        """
        if shutter_speed is None or focal_length is None:
            return 50.0  # Neutral for missing data

        if focal_length == 0:
            return 50.0  # Invalid data

        # Reciprocal rule threshold (assume full-frame, crop_factor=1)
        min_speed = 1.0 / focal_length

        # Calculate safety margin
        if shutter_speed <= min_speed / 2:
            return 100.0  # 2x faster than rule
        elif shutter_speed <= min_speed:
            return 80.0   # Meets rule
        elif shutter_speed <= min_speed * 2:
            return 60.0   # Risky but possible
        else:
            return 40.0   # Likely camera shake

    def _score_aperture(self, aperture: Optional[float]) -> float:
        """
        Score aperture for optimal sharpness (0-100).

        Mid-range apertures (f/5.6-f/11) are typically sharpest.
        Wide open (f/1.4-f/2.8) and very stopped down (f/16+) reduce sharpness.

        Scoring:
        - f/5.6-f/11: 100 points (optimal sharpness)
        - f/4-f/5.6, f/11-f/16: 80 points (good)
        - f/2.8-f/4, f/16-f/22: 60 points (acceptable)
        - f/1.4-f/2.8, f/22+: 40 points (reduced sharpness)
        - Missing: 50 points (neutral)

        Args:
            aperture: F-stop value (e.g., 2.8, 5.6, 11.0)

        Returns:
            Score 0-100
        """
        if aperture is None:
            return 50.0  # Neutral for missing data

        if 5.6 <= aperture <= 11.0:
            return 100.0  # Optimal range
        elif (4.0 <= aperture < 5.6) or (11.0 < aperture <= 16.0):
            return 80.0   # Good range
        elif (2.8 <= aperture < 4.0) or (16.0 < aperture <= 22.0):
            return 60.0   # Acceptable
        else:
            return 40.0   # Extreme apertures

    def _score_exposure_comp(self, exposure_comp: Optional[float]) -> float:
        """
        Score exposure compensation (0-100).

        Small exposure adjustments indicate proper metering.
        Large adjustments may indicate difficult lighting or incorrect settings.

        Scoring:
        - ±0 to ±0.5 stops: 100 points (well-exposed)
        - ±0.5 to ±1.0 stops: 80 points (minor adjustment)
        - ±1.0 to ±2.0 stops: 60 points (significant adjustment)
        - ±2.0+ stops: 40 points (extreme correction)
        - Missing: 50 points (neutral)

        Args:
            exposure_comp: Exposure compensation in stops (e.g., -0.5, +1.0)

        Returns:
            Score 0-100
        """
        if exposure_comp is None:
            return 50.0  # Neutral for missing data

        abs_comp = abs(exposure_comp)

        if abs_comp <= 0.5:
            return 100.0  # Minimal adjustment
        elif abs_comp <= 1.0:
            return 80.0   # Small adjustment
        elif abs_comp <= 2.0:
            return 60.0   # Moderate adjustment
        else:
            return 40.0   # Large adjustment

    def _score_flash(self, flash_fired: Optional[bool]) -> float:
        """
        Score flash usage (0-100).

        Natural light generally preferred for quality.
        Flash can cause harsh shadows, red-eye, and unnatural lighting.

        Scoring:
        - No flash: 100 points (natural light preferred)
        - Flash fired: 70 points (acceptable but not ideal)
        - Missing: 50 points (neutral)

        Args:
            flash_fired: True if flash was used, False otherwise

        Returns:
            Score 0-100
        """
        if flash_fired is None:
            return 50.0  # Neutral for missing data

        if flash_fired:
            return 70.0  # Flash used (acceptable but not ideal)
        else:
            return 100.0  # Natural light (preferred)

    # ========================================================================
    # Temporal Partitioning Helpers
    # ========================================================================

    def _partition_by_time(self, items: list, bucket_count: int) -> list[list]:
        """
        Partition items into temporal buckets.

        Args:
            items: List of LibraryItem objects (sorted chronologically)
            bucket_count: Number of buckets to create

        Returns:
            List of buckets, each containing items from that time period

        Algorithm:
        1. Find time span (first to last item)
        2. Divide span into equal buckets
        3. Assign each item to its bucket
        """
        if not items or bucket_count <= 0:
            return []

        # Initialize buckets
        buckets = [[] for _ in range(bucket_count)]

        # Find time range
        start_time = items[0].created_date
        end_time = items[-1].created_date
        time_span = (end_time - start_time).total_seconds()

        if time_span == 0:
            # All items at same time - put in first bucket
            buckets[0] = items
            return buckets

        # Assign items to buckets
        for item in items:
            # Calculate bucket index
            elapsed = (item.created_date - start_time).total_seconds()
            bucket_idx = int((elapsed / time_span) * (bucket_count - 1))
            bucket_idx = min(bucket_idx, bucket_count - 1)  # Clamp to valid range
            buckets[bucket_idx].append(item)

        # Filter out empty buckets
        non_empty_buckets = [b for b in buckets if b]
        return non_empty_buckets
