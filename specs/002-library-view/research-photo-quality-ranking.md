# Research: EXIF-Based Photo Quality Ranking and Event Clustering

**Date**: 2025-10-19
**Context**: Library view implementation for photo_organiser
**Objective**: Identify simple, EXIF-based algorithms for photo quality scoring and time-based event clustering

---

## Executive Summary

This research evaluates practical approaches for identifying "best shots" using only EXIF metadata (no ML/AI) and clustering photos into events based on timestamps. The recommended approach combines a weighted scoring system for photo quality with gap-based temporal clustering.

**Key Finding**: EXIF metadata alone cannot assess actual image quality (sharpness, composition), but can identify photos with *optimal technical settings* that correlate with quality under good shooting conditions.

---

## 1. Photo Quality Assessment

### 1.1 Research Findings

**EXIF Limitations**:
- EXIF data records camera settings at capture time but cannot determine actual image quality
- A photo with "optimal" settings can still be blurry (wrong focus, subject motion, camera shake)
- Quality assessment from EXIF is inherently heuristic and probabilistic

**Viable Quality Indicators**:

1. **ISO Sensitivity** (ISOSpeedRatings)
   - Lower ISO = less noise, better image quality
   - Range typically: 100-6400 (modern cameras), 100-51200 (high-end)
   - Rule: ISO 100-400 = excellent, 800-1600 = good, 3200+ = acceptable/poor

2. **Camera Shake Risk** (ExposureTime + FocalLength)
   - Reciprocal rule: minimum shutter speed = 1/focal_length
   - Below this threshold = increased shake risk
   - Example: 100mm lens needs ≥1/100s; 50mm lens needs ≥1/50s
   - Modern adjustment: For high-res sensors, use 1/(focal_length × 2)

3. **Aperture** (FNumber)
   - Mid-range apertures (f/5.6-f/11) often sharpest for most lenses
   - Very wide (f/1.4-f/2.8) = shallow DOF, potential softness
   - Very narrow (f/16-f/22) = diffraction softening
   - Context-dependent: portraits prefer wide, landscapes prefer narrow

4. **Exposure Compensation** (ExposureCompensation)
   - Indicates photographer's intentional adjustment
   - Near zero = camera auto-exposure accepted
   - Significant values (±1-2 EV) = deliberate creative choice or difficult conditions

5. **Flash Usage** (Flash)
   - Flash fired = potentially harsh lighting or low-light conditions
   - Natural light often preferred aesthetically
   - Context-dependent (event photography vs. landscape)

**Camera-Specific Quality Hints**:
- Some manufacturers provide quality indicators in maker notes
- Not standardized across brands (Canon/Nikon/Sony differ)
- Reliability varies; not recommended for general implementation

### 1.2 Recommended Approach: Weighted Technical Quality Score

**Decision**: Use a weighted scoring system combining multiple EXIF indicators.

**Rationale**:
- Simple to implement and understand
- Deterministic and debuggable
- Explainable to users ("This photo scored well because of low ISO and good exposure")
- No external dependencies or ML models
- Fast computation suitable for view rendering

**Formula** (0-100 scale):

```
quality_score = (iso_score × 0.40) +
                (shake_score × 0.30) +
                (aperture_score × 0.15) +
                (exposure_comp_score × 0.10) +
                (flash_score × 0.05)
```

**Weighting rationale**:
- ISO (40%): Strongest technical quality indicator
- Shake risk (30%): Critical for sharpness
- Aperture (15%): Moderate impact, lens-dependent
- Exposure compensation (10%): Indicates intentional adjustment
- Flash (5%): Minor aesthetic preference

### 1.3 Scoring Component Details

#### ISO Score (0-100)
```python
def calculate_iso_score(iso_value):
    """
    Lower ISO = higher score
    Baseline: ISO 100 = 100 points, ISO 6400 = 0 points
    """
    if iso_value is None:
        return 50  # neutral default

    # Clamp to reasonable range
    iso = max(100, min(6400, iso_value))

    # Linear interpolation: 100=100pts, 6400=0pts
    score = 100 - ((iso - 100) / 6300) * 100

    return max(0, min(100, score))
```

#### Camera Shake Score (0-100)
```python
def calculate_shake_score(exposure_time, focal_length, has_stabilization=False):
    """
    Based on reciprocal rule: 1/focal_length
    Accounts for image stabilization (+2-5 stops)
    """
    if exposure_time is None or focal_length is None:
        return 50  # neutral default

    # Convert exposure time to fraction (e.g., 0.004 = 1/250)
    if exposure_time > 1:
        exposure_time = 1 / exposure_time

    # Reciprocal rule threshold (adjusted for high-res sensors)
    min_safe_speed = 1 / (focal_length * 2)

    # Adjust for image stabilization (assume 3 stops = 8x slower OK)
    if has_stabilization:
        min_safe_speed = min_safe_speed / 8

    # Calculate how much faster than minimum
    safety_ratio = min_safe_speed / exposure_time

    if safety_ratio >= 1.0:
        # Faster than minimum - safe
        score = 100
    elif safety_ratio >= 0.5:
        # Within 1 stop of minimum - acceptable
        score = 70 + (safety_ratio - 0.5) * 60
    else:
        # Slower than minimum - risky
        score = safety_ratio * 140

    return max(0, min(100, score))
```

#### Aperture Score (0-100)
```python
def calculate_aperture_score(f_number):
    """
    Favors mid-range apertures (f/5.6-f/11)
    Penalizes extremes (diffraction or softness)
    """
    if f_number is None:
        return 50  # neutral default

    # Optimal range: f/5.6 to f/11
    if 5.6 <= f_number <= 11:
        score = 100
    elif 4 <= f_number < 5.6:
        # Wide apertures: gradual reduction
        score = 70 + ((f_number - 4) / 1.6) * 30
    elif 11 < f_number <= 16:
        # Narrow apertures: gradual reduction
        score = 70 + ((16 - f_number) / 5) * 30
    elif 2.8 <= f_number < 4:
        # Very wide: moderate reduction
        score = 50 + ((f_number - 2.8) / 1.2) * 20
    elif 16 < f_number <= 22:
        # Very narrow: diffraction penalty
        score = 40 + ((22 - f_number) / 6) * 30
    else:
        # Extreme apertures
        score = 30

    return max(0, min(100, score))
```

#### Exposure Compensation Score (0-100)
```python
def calculate_exposure_comp_score(exposure_compensation):
    """
    Small adjustments = intentional, larger = difficult conditions
    Zero or near-zero is neutral
    """
    if exposure_compensation is None:
        return 50  # neutral default

    # Convert to absolute value
    abs_comp = abs(exposure_compensation)

    if abs_comp <= 0.3:
        # Minimal adjustment - optimal
        score = 100
    elif abs_comp <= 1.0:
        # Small adjustment - good
        score = 80
    elif abs_comp <= 2.0:
        # Moderate adjustment - acceptable
        score = 60 - (abs_comp - 1.0) * 20
    else:
        # Large adjustment - challenging conditions
        score = 40

    return max(0, min(100, score))
```

#### Flash Score (0-100)
```python
def calculate_flash_score(flash_fired):
    """
    Slight preference for natural light
    Not heavily weighted as flash has valid uses
    """
    if flash_fired is None:
        return 50  # neutral default

    if flash_fired:
        return 40  # Flash used - slight penalty
    else:
        return 60  # Natural light - slight bonus
```

### 1.4 Complete Implementation Example

```python
from PIL import Image
from PIL.ExifTags import TAGS
import exifread

def extract_quality_exif(image_path):
    """
    Extract EXIF fields needed for quality scoring.
    Returns dict with standardized field names.
    """
    try:
        # Try with Pillow first (faster, built into project)
        img = Image.open(image_path)
        exif = img.getexif()

        if not exif:
            return None

        # Map tag IDs to names and extract relevant fields
        exif_dict = {}
        for tag_id, value in exif.items():
            tag_name = TAGS.get(tag_id, tag_id)
            exif_dict[tag_name] = value

        # Extract relevant fields with type conversion
        result = {
            'iso': exif_dict.get('ISOSpeedRatings'),
            'exposure_time': None,
            'focal_length': exif_dict.get('FocalLength'),
            'f_number': exif_dict.get('FNumber'),
            'exposure_compensation': exif_dict.get('ExposureCompensation'),
            'flash': exif_dict.get('Flash', 0) & 0x1 == 1,  # Check if flash fired bit
        }

        # Handle exposure time (can be fraction or decimal)
        if 'ExposureTime' in exif_dict:
            exp_time = exif_dict['ExposureTime']
            if isinstance(exp_time, tuple):
                result['exposure_time'] = exp_time[0] / exp_time[1]
            else:
                result['exposure_time'] = exp_time

        return result

    except Exception as e:
        print(f"Error extracting EXIF from {image_path}: {e}")
        return None


def calculate_photo_quality_score(image_path):
    """
    Calculate overall quality score (0-100) for a photo.
    Returns tuple: (score, explanation_dict)
    """
    exif_data = extract_quality_exif(image_path)

    if not exif_data:
        # No EXIF data - neutral score
        return 50, {"reason": "No EXIF data available"}

    # Calculate individual component scores
    iso_score = calculate_iso_score(exif_data['iso'])
    shake_score = calculate_shake_score(
        exif_data['exposure_time'],
        exif_data['focal_length']
    )
    aperture_score = calculate_aperture_score(exif_data['f_number'])
    exp_comp_score = calculate_exposure_comp_score(
        exif_data['exposure_compensation']
    )
    flash_score = calculate_flash_score(exif_data['flash'])

    # Weighted combination
    total_score = (
        iso_score * 0.40 +
        shake_score * 0.30 +
        aperture_score * 0.15 +
        exp_comp_score * 0.10 +
        flash_score * 0.05
    )

    # Return score and explanation
    explanation = {
        'iso_score': iso_score,
        'shake_score': shake_score,
        'aperture_score': aperture_score,
        'exposure_comp_score': exp_comp_score,
        'flash_score': flash_score,
        'iso_value': exif_data['iso'],
        'exposure_time': exif_data['exposure_time'],
        'focal_length': exif_data['focal_length'],
        'f_number': exif_data['f_number'],
    }

    return round(total_score, 1), explanation


def select_best_shots(photos, top_n=3):
    """
    Select the N best photos from a collection based on quality scores.

    Args:
        photos: List of photo paths
        top_n: Number of best shots to return

    Returns:
        List of (photo_path, score, explanation) tuples
    """
    scored_photos = []

    for photo_path in photos:
        score, explanation = calculate_photo_quality_score(photo_path)
        scored_photos.append((photo_path, score, explanation))

    # Sort by score descending and return top N
    scored_photos.sort(key=lambda x: x[1], reverse=True)
    return scored_photos[:top_n]
```

### 1.5 Edge Cases and Handling

#### Missing EXIF Fields
```python
# Default strategy: Use neutral score (50) for missing fields
# This prevents photos without full EXIF from being unfairly penalized
# Alternative: Could weight remaining fields more heavily

def handle_missing_exif(exif_data):
    """Provide defaults for missing EXIF fields"""
    defaults = {
        'iso': None,  # Will score as 50 (neutral)
        'exposure_time': None,
        'focal_length': None,
        'f_number': None,
        'exposure_compensation': 0,  # Assume no compensation
        'flash': False,  # Assume no flash
    }

    return {**defaults, **exif_data}
```

#### Different Camera Models
```python
# Challenge: Different cameras have different ISO ranges
# Solution: Use normalized scoring based on typical ranges
# Advanced: Could build per-camera profiles, but adds complexity

def normalize_iso_for_camera(iso_value, camera_model=None):
    """
    Normalize ISO based on camera capabilities.
    Simple version: use universal range (100-6400)
    Advanced version: adjust range per camera
    """
    # For simplicity, use universal range
    # Could extend with camera-specific ranges:
    # camera_ranges = {
    #     'Canon EOS R5': (100, 51200),
    #     'Sony A7III': (100, 51200),
    #     'iPhone 12': (32, 3072),
    # }

    return iso_value
```

#### Video Files
```python
def calculate_video_quality_score(video_path):
    """
    Videos have different quality indicators.
    Consider: bitrate, resolution, frame rate instead.
    """
    # For MVP: return neutral score or skip quality ranking for videos
    # Videos typically don't have same EXIF as photos

    try:
        # Could use ffprobe or similar to get video metadata
        # For now, return neutral score
        return 50, {"reason": "Video quality scoring not yet implemented"}
    except Exception as e:
        return 50, {"reason": f"Error: {e}"}
```

### 1.6 Validation and Testing Strategy

```python
def validate_quality_scoring():
    """
    Test quality scoring with known-good and known-bad examples.
    """
    test_cases = [
        {
            'name': 'Ideal daylight photo',
            'exif': {
                'iso': 100,
                'exposure_time': 1/500,
                'focal_length': 50,
                'f_number': 8.0,
                'exposure_compensation': 0,
                'flash': False,
            },
            'expected_score_range': (85, 100),
        },
        {
            'name': 'High ISO low light',
            'exif': {
                'iso': 6400,
                'exposure_time': 1/60,
                'focal_length': 50,
                'f_number': 2.8,
                'exposure_compensation': 0,
                'flash': True,
            },
            'expected_score_range': (30, 50),
        },
        {
            'name': 'Camera shake risk',
            'exif': {
                'iso': 400,
                'exposure_time': 1/30,  # Too slow for 200mm
                'focal_length': 200,
                'f_number': 5.6,
                'exposure_compensation': 0,
                'flash': False,
            },
            'expected_score_range': (40, 60),
        },
    ]

    for test in test_cases:
        # Score would be calculated here
        pass
```

---

## 2. Time-Based Event Clustering

### 2.1 Research Findings

**Academic Approaches**:
- Research papers propose sophisticated multi-modal clustering (time + location + content)
- Commercial tools (Google Photos, Adobe Lightroom) use ML-based event detection
- Simple gap-based approaches are common in practice and effective

**Key Insight**: Gap-based temporal clustering is simple, fast, and produces intuitive results for users. A photo session typically has a natural gap (hours) before the next session.

### 2.2 Recommended Approach: Adaptive Gap-Based Clustering

**Decision**: Use adaptive gap-based clustering with configurable thresholds.

**Rationale**:
- Extremely simple to implement and understand
- Fast O(n) time complexity (single pass through sorted photos)
- Deterministic results
- Easy to tune and adjust based on user feedback
- No external dependencies

**Algorithm**:

```
1. Sort photos by capture timestamp
2. Iterate through sorted photos
3. If gap between consecutive photos > threshold:
   - Start new event/cluster
4. Otherwise:
   - Add to current event/cluster
5. Handle date boundaries (optional: force new cluster at midnight)
```

### 2.3 Gap Threshold Selection

**Research-Based Recommendations**:

| Time Period | Recommended Gap | Rationale |
|-------------|-----------------|-----------|
| Days view | 1-2 hours | Multiple photo sessions in one day |
| Months view | 3-4 hours | Distinct events/occasions |
| Years view | 1 day | Major events span days |

**Adaptive Strategy**:
```python
def determine_event_gap(photo_density):
    """
    Adjust gap threshold based on photo density.
    High density (many photos per day) = shorter gaps
    Low density (few photos per day) = longer gaps
    """
    if photo_density > 50:  # photos per day
        return 1.0  # 1 hour
    elif photo_density > 20:
        return 2.0  # 2 hours
    else:
        return 4.0  # 4 hours
```

### 2.4 Complete Implementation Example

```python
from datetime import datetime, timedelta
from typing import List, Tuple
from collections import defaultdict

class PhotoEvent:
    """Represents a clustered event/group of photos"""

    def __init__(self, start_time: datetime):
        self.start_time = start_time
        self.end_time = start_time
        self.photos = []

    def add_photo(self, photo_path: str, timestamp: datetime):
        """Add a photo to this event"""
        self.photos.append((photo_path, timestamp))
        if timestamp > self.end_time:
            self.end_time = timestamp

    def duration_hours(self) -> float:
        """Get event duration in hours"""
        delta = self.end_time - self.start_time
        return delta.total_seconds() / 3600

    def __repr__(self):
        return f"PhotoEvent({self.start_time}, {len(self.photos)} photos)"


def cluster_photos_by_time_gap(
    photos: List[Tuple[str, datetime]],
    gap_hours: float = 2.0,
    force_date_boundaries: bool = False
) -> List[PhotoEvent]:
    """
    Cluster photos into events based on time gaps.

    Args:
        photos: List of (photo_path, timestamp) tuples
        gap_hours: Maximum time gap within an event (hours)
        force_date_boundaries: If True, force new event at midnight

    Returns:
        List of PhotoEvent objects
    """
    if not photos:
        return []

    # Sort by timestamp
    sorted_photos = sorted(photos, key=lambda x: x[1])

    events = []
    current_event = PhotoEvent(sorted_photos[0][1])
    current_event.add_photo(sorted_photos[0][0], sorted_photos[0][1])

    gap_threshold = timedelta(hours=gap_hours)

    for photo_path, timestamp in sorted_photos[1:]:
        prev_timestamp = current_event.end_time
        time_gap = timestamp - prev_timestamp

        # Check for date boundary (if enabled)
        date_boundary = (
            force_date_boundaries and
            timestamp.date() != prev_timestamp.date()
        )

        # Start new event if gap exceeds threshold or date boundary
        if time_gap > gap_threshold or date_boundary:
            events.append(current_event)
            current_event = PhotoEvent(timestamp)

        current_event.add_photo(photo_path, timestamp)

    # Don't forget the last event
    events.append(current_event)

    return events


def cluster_photos_for_months_view(photos_in_month: List[Tuple[str, datetime]]) -> List[PhotoEvent]:
    """
    Cluster photos within a month into significant events.
    Uses slightly longer gap threshold for month-level grouping.
    """
    return cluster_photos_by_time_gap(
        photos_in_month,
        gap_hours=3.0,  # 3-hour gap for monthly events
        force_date_boundaries=True  # Events shouldn't span midnight
    )


def cluster_photos_for_days_view(photos_in_day: List[Tuple[str, datetime]]) -> List[PhotoEvent]:
    """
    Cluster photos within a single day into sessions.
    Uses shorter gap threshold for fine-grained grouping.
    """
    return cluster_photos_by_time_gap(
        photos_in_day,
        gap_hours=1.5,  # 1.5-hour gap for daily sessions
        force_date_boundaries=False  # All in same day already
    )


def organize_photos_by_month(all_photos: List[Tuple[str, datetime]]) -> dict:
    """
    Organize photos by month, with events within each month.

    Returns:
        Dict mapping (year, month) -> List[PhotoEvent]
    """
    # Group by month
    months = defaultdict(list)
    for photo_path, timestamp in all_photos:
        month_key = (timestamp.year, timestamp.month)
        months[month_key].append((photo_path, timestamp))

    # Cluster each month's photos into events
    month_events = {}
    for month_key, photos in months.items():
        month_events[month_key] = cluster_photos_for_months_view(photos)

    return month_events


def organize_photos_by_day(all_photos: List[Tuple[str, datetime]]) -> dict:
    """
    Organize photos by day, with sessions within each day.

    Returns:
        Dict mapping (year, month, day) -> List[PhotoEvent]
    """
    # Group by day
    days = defaultdict(list)
    for photo_path, timestamp in all_photos:
        day_key = (timestamp.year, timestamp.month, timestamp.day)
        days[day_key].append((photo_path, timestamp))

    # Cluster each day's photos into sessions
    day_sessions = {}
    for day_key, photos in days.items():
        day_sessions[day_key] = cluster_photos_for_days_view(photos)

    return day_sessions
```

### 2.5 Edge Cases and Handling

#### Events Spanning Midnight

```python
def handle_midnight_spanning_events(
    photos: List[Tuple[str, datetime]],
    gap_hours: float = 2.0
):
    """
    Example: Party from 10 PM to 2 AM - should this be one event or two?

    Strategy options:
    1. Force split at midnight (simpler, more predictable)
    2. Allow spanning if gap < threshold (more natural, but complex)

    Recommendation: Force split at midnight for Days view,
    allow spanning for Months view
    """
    # Implementation depends on force_date_boundaries parameter
    pass
```

#### Very Dense Photo Sessions

```python
def handle_burst_mode_photos(photos: List[Tuple[str, datetime]]):
    """
    Burst mode can create hundreds of photos in seconds.
    These should all be in same event.

    Gap-based clustering naturally handles this (gaps are tiny).
    No special handling needed.
    """
    pass
```

#### Sparse Photo Collections

```python
def handle_sparse_photos(photos: List[Tuple[str, datetime]]):
    """
    User takes 1 photo per week - each becomes its own event.

    This is actually desired behavior - each photo IS an event.
    Could add minimum photos per event filter if needed.
    """
    events = cluster_photos_by_time_gap(photos, gap_hours=2.0)

    # Optional: filter out single-photo events
    # meaningful_events = [e for e in events if len(e.photos) > 1]

    return events
```

#### Photos Without Timestamps

```python
def handle_missing_timestamps(photo_path: str):
    """
    Photos without EXIF date - fallback to file modification time.
    """
    import os
    from datetime import datetime

    # Try EXIF first
    exif_date = extract_exif_date(photo_path)
    if exif_date:
        return exif_date

    # Fallback to file modification time
    mod_time = os.path.getmtime(photo_path)
    return datetime.fromtimestamp(mod_time)


def extract_exif_date(photo_path: str) -> datetime:
    """Extract capture date from EXIF"""
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS

        img = Image.open(photo_path)
        exif = img.getexif()

        if exif:
            for tag_id, value in exif.items():
                tag_name = TAGS.get(tag_id, tag_id)
                if tag_name == 'DateTime' or tag_name == 'DateTimeOriginal':
                    # Parse EXIF datetime format: "2023:10:19 14:30:45"
                    return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")

        return None
    except Exception:
        return None
```

### 2.6 Performance Considerations

```python
def efficient_photo_clustering(all_photos: List[Tuple[str, datetime]]):
    """
    For large libraries (50,000+ photos), clustering must be efficient.

    Time complexity: O(n log n) for sorting + O(n) for clustering = O(n log n)
    Space complexity: O(n) for storing events

    This is acceptable for rendering views.
    """

    # Pre-sort once
    sorted_photos = sorted(all_photos, key=lambda x: x[1])

    # Single-pass clustering
    events = cluster_photos_by_time_gap(sorted_photos, gap_hours=2.0)

    return events


def cache_event_clustering(library_db):
    """
    For performance, cache event clustering results.
    Invalidate cache when:
    - New photos added
    - Photos deleted
    - Timestamps changed
    """
    # Could store in SQLite or similar
    # cache_key = hash(sorted(photo_timestamps))
    pass
```

---

## 3. Integration with Library Views

### 3.1 Days View Implementation

```python
def generate_days_view(all_photos: List[Tuple[str, datetime, str]]):
    """
    Generate Days view with best shots highlighted.

    Args:
        all_photos: List of (photo_path, timestamp, thumbnail_path) tuples

    Returns:
        List of day data with best shots identified
    """
    from collections import defaultdict

    # Group photos by day
    days = defaultdict(list)
    for photo_path, timestamp, thumbnail_path in all_photos:
        day_key = timestamp.date()
        days[day_key].append(photo_path)

    # For each day, find best shots
    days_data = []
    for day_key in sorted(days.keys(), reverse=True):
        photos = days[day_key]

        # Score all photos in this day
        best_shots = select_best_shots(photos, top_n=3)

        days_data.append({
            'date': day_key,
            'total_photos': len(photos),
            'best_shots': best_shots,
            'all_photos': photos,
        })

    return days_data
```

### 3.2 Months View Implementation

```python
def generate_months_view(all_photos: List[Tuple[str, datetime, str]]):
    """
    Generate Months view with event-based clustering.
    """
    # Organize by month and cluster into events
    month_events = organize_photos_by_month(
        [(path, ts) for path, ts, _ in all_photos]
    )

    months_data = []
    for (year, month), events in sorted(month_events.items(), reverse=True):

        # For each event in the month, find best shot
        event_highlights = []
        for event in events:
            event_photos = [photo_path for photo_path, _ in event.photos]
            best_shot = select_best_shots(event_photos, top_n=1)[0]

            event_highlights.append({
                'start_time': event.start_time,
                'duration_hours': event.duration_hours(),
                'photo_count': len(event.photos),
                'best_shot': best_shot,
            })

        months_data.append({
            'year': year,
            'month': month,
            'events': event_highlights,
            'total_photos': sum(len(e.photos) for e in events),
        })

    return months_data
```

### 3.3 Years View Implementation

```python
def generate_years_view(all_photos: List[Tuple[str, datetime, str]]):
    """
    Generate Years view with highlights spread across the year.

    Strategy: Select top N photos per year, ensuring temporal variety.
    """
    from collections import defaultdict

    # Group by year
    years = defaultdict(list)
    for photo_path, timestamp, _ in all_photos:
        years[timestamp.year].append((photo_path, timestamp))

    years_data = []
    for year in sorted(years.keys(), reverse=True):
        photos = years[year]

        # Score all photos
        scored_photos = [(p, *calculate_photo_quality_score(p))
                        for p, _ in photos]

        # Select highlights with temporal diversity
        highlights = select_yearly_highlights(
            scored_photos,
            timestamps=[ts for _, ts in photos],
            target_count=30
        )

        years_data.append({
            'year': year,
            'total_photos': len(photos),
            'highlights': highlights,
        })

    return years_data


def select_yearly_highlights(
    scored_photos: List[Tuple[str, float, dict]],
    timestamps: List[datetime],
    target_count: int = 30
):
    """
    Select highlights ensuring temporal variety.

    Strategy:
    1. Sort by quality score
    2. Greedily select high-scoring photos
    3. Penalize photos too close in time to already-selected photos
    """
    if len(scored_photos) <= target_count:
        return scored_photos

    # Sort by quality score
    sorted_photos = sorted(
        zip(scored_photos, timestamps),
        key=lambda x: x[0][1],
        reverse=True
    )

    selected = []
    min_gap_days = 7  # Prefer photos at least 1 week apart

    for (photo_path, score, explanation), timestamp in sorted_photos:
        # Check temporal diversity
        too_close = any(
            abs((timestamp - sel_ts).days) < min_gap_days
            for _, sel_ts in selected
        )

        if not too_close or len(selected) < target_count // 2:
            selected.append(((photo_path, score, explanation), timestamp))

        if len(selected) >= target_count:
            break

    # If we still need more, add next highest scoring regardless of gap
    if len(selected) < target_count:
        for item in sorted_photos:
            if item not in selected:
                selected.append(item)
                if len(selected) >= target_count:
                    break

    return [photo_data for photo_data, _ in selected]
```

---

## 4. Alternatives Considered

### 4.1 Machine Learning Approaches

**Description**: Use pre-trained ML models (NIMA, BRISQUE) for aesthetic quality assessment.

**Pros**:
- Can assess actual image content (composition, subject, aesthetics)
- More accurate quality predictions
- Industry standard for commercial tools

**Cons**:
- Requires ML dependencies (TensorFlow, PyTorch)
- Slow inference (100-500ms per image)
- Not explainable to users
- Complex to maintain and debug

**Verdict**: Rejected - violates simplicity and explainability requirements.

### 4.2 Content-Based Clustering

**Description**: Cluster photos by visual similarity using feature extraction.

**Pros**:
- Can group similar shots (e.g., same location, same people)
- More sophisticated than pure time-based clustering

**Cons**:
- Computationally expensive
- Requires image processing libraries
- Results less intuitive for users ("why are these grouped?")
- Added complexity

**Verdict**: Rejected - time-based clustering is simpler and sufficient for MVP.

### 4.3 User Rating System

**Description**: Let users manually rate photos, use ratings for "best shots".

**Pros**:
- Personalized to user preferences
- Accurate for subjective quality

**Cons**:
- Requires manual effort from user
- Cold start problem (no ratings initially)
- Not suitable for auto-highlighting at scale

**Verdict**: Deferred - good future enhancement, but need automatic baseline first.

### 4.4 Heuristic Rules Only (No Scoring)

**Description**: Use simple boolean rules (e.g., "ISO < 800 AND shutter fast enough").

**Pros**:
- Extremely simple
- Fast computation

**Cons**:
- Too rigid, misses nuance
- Can't rank photos (binary yes/no)
- Doesn't combine multiple factors well

**Verdict**: Rejected - weighted scoring provides better granularity.

---

## 5. Recommendations and Next Steps

### 5.1 Implementation Priorities

1. **Immediate (P1)**:
   - Implement basic quality scoring for Days view
   - Use ISO + shake risk only (simplified)
   - Test with real photo collection

2. **Short-term (P2)**:
   - Add gap-based clustering for Months view
   - Implement full quality scoring (all 5 components)
   - Add caching for computed scores

3. **Medium-term (P3)**:
   - Implement Years view highlights with temporal diversity
   - Add user-configurable gap thresholds
   - Performance optimization for large libraries

4. **Future**:
   - Consider ML-based scoring as optional enhancement
   - User feedback system to improve scoring
   - Camera-specific tuning profiles

### 5.2 Configuration Recommendations

```python
# config.py
QUALITY_SCORING = {
    'weights': {
        'iso': 0.40,
        'shake': 0.30,
        'aperture': 0.15,
        'exposure_comp': 0.10,
        'flash': 0.05,
    },
    'iso_range': (100, 6400),
    'optimal_aperture_range': (5.6, 11),
}

EVENT_CLUSTERING = {
    'days_view_gap_hours': 1.5,
    'months_view_gap_hours': 3.0,
    'force_date_boundaries_days': False,
    'force_date_boundaries_months': True,
}

YEARLY_HIGHLIGHTS = {
    'target_count_per_year': 30,
    'min_temporal_gap_days': 7,
}
```

### 5.3 Testing Strategy

```python
# Test cases to validate
test_scenarios = [
    "Day with 100 photos - verify top 3 have best ISO/shutter",
    "Month with 3 distinct events - verify correct clustering",
    "Year with sparse photos - verify temporal diversity",
    "Photos without EXIF - verify fallback to file dates",
    "Burst mode sequence - verify single event cluster",
    "Midnight-spanning event - verify date boundary behavior",
]
```

### 5.4 Performance Targets

- Quality scoring: < 10ms per photo (for view rendering)
- Event clustering: < 100ms for 10,000 photos
- Cache hit rate: > 90% for repeat views
- Memory usage: < 100MB for clustering metadata

---

## 6. References and Resources

### Academic Papers
- "Temporal event clustering for digital photo collections" (ACM 2005)
- Gap-based clustering algorithms for time series data

### Industry Implementations
- **Excire Foto**: AI-assisted culling with sharpness and aesthetic ratings
- **Google Photos**: Photo stacks with automatic "best" selection
- **Adobe Lightroom**: EXIF-based filtering and metadata organization

### Technical Resources
- **Reciprocal Rule**: Camera shake prevention (1/focal_length minimum shutter speed)
- **EXIF Standards**: Exchangeable image file format specifications
- **Python Libraries**: PIL/Pillow, exifread for metadata extraction

### Photography Guidelines
- ISO quality impact: Lower = better image quality
- Aperture sweet spot: f/5.6-f/11 for most lenses
- Exposure triangle: ISO + aperture + shutter speed relationship

---

## Appendix A: EXIF Field Reference

### Standard EXIF Tags for Quality Assessment

| EXIF Tag | Type | Purpose | Example Values |
|----------|------|---------|----------------|
| ISOSpeedRatings | Integer | Sensor sensitivity | 100, 400, 1600, 6400 |
| ExposureTime | Rational | Shutter speed | 1/500, 1/60, 2.5 |
| FNumber | Rational | Aperture | 1.8, 5.6, 11.0, 22.0 |
| FocalLength | Rational | Lens focal length | 24, 50, 200, 400 (mm) |
| ExposureCompensation | SRational | Exposure adjustment | -2.0, 0.0, +1.3 (EV) |
| Flash | Integer | Flash status | 0 (no flash), 1 (flash fired) |
| DateTimeOriginal | String | Capture timestamp | "2023:10:19 14:30:45" |
| LensModel | String | Lens identification | "EF 24-70mm f/2.8L" |
| Make | String | Camera manufacturer | "Canon", "Nikon", "Sony" |
| Model | String | Camera model | "EOS R5", "Z6 II" |

### Accessing EXIF with Python

```python
# Using Pillow
from PIL import Image
from PIL.ExifTags import TAGS

img = Image.open('photo.jpg')
exif = img.getexif()
exif_dict = {TAGS.get(tag_id, tag_id): value
             for tag_id, value in exif.items()}

# Using exifread
import exifread

with open('photo.jpg', 'rb') as f:
    tags = exifread.process_file(f)
```

---

## Appendix B: Example Scoring Results

### High-Quality Photo Example
```
File: IMG_1234.jpg
ISO: 100
Shutter: 1/500s
Focal Length: 50mm
Aperture: f/8
Exposure Comp: 0
Flash: No

Scores:
- ISO Score: 100 (perfect)
- Shake Score: 100 (very safe shutter speed)
- Aperture Score: 100 (optimal range)
- Exposure Comp Score: 100 (no adjustment needed)
- Flash Score: 60 (natural light bonus)

Overall Quality Score: 95.5
```

### Low-Quality Photo Example
```
File: IMG_9999.jpg
ISO: 6400
Shutter: 1/30s
Focal Length: 200mm
Aperture: f/2.8
Exposure Comp: -2.0
Flash: Yes

Scores:
- ISO Score: 0 (very high ISO)
- Shake Score: 15 (significant shake risk)
- Aperture Score: 50 (wide open)
- Exposure Comp Score: 40 (large adjustment)
- Flash Score: 40 (flash used)

Overall Quality Score: 17.3
```

---

## Document History

- **2025-10-19**: Initial research completed
- **Focus**: EXIF-based quality scoring and time-based event clustering
- **Recommendation**: Weighted scoring system + gap-based clustering
