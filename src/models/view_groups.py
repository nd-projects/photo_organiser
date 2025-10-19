"""
View group models for organizing library items by time periods.

This module defines the grouping entities (DayGroup, MonthGroup, YearGroup, EventCluster)
used to organize library items for different view modes.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .library_item import LibraryItem


@dataclass
class EventCluster:
    """Collection of media items from a single event (time-based clustering)."""

    # Items
    items: list['LibraryItem']      # All media in this event (chronological order)

    # Time boundaries
    start_time: datetime            # First photo timestamp
    end_time: datetime              # Last photo timestamp

    # Statistics
    photo_count: int                # Number of photos
    video_count: int                # Number of videos

    def __post_init__(self):
        """Validation and derived data."""
        assert len(self.items) > 0, "EventCluster must have at least one item"
        assert self.start_time <= self.end_time, "Invalid time range"
        # Ensure items are sorted chronologically
        self.items.sort(key=lambda x: x.created_date)

    @property
    def duration(self) -> float:
        """Event duration in hours."""
        return (self.end_time - self.start_time).total_seconds() / 3600

    @property
    def display_time_range(self) -> str:
        """Human-readable time range for UI display."""
        if self.start_time.date() == self.end_time.date():
            # Same day: "2:30 PM - 5:45 PM"
            return f"{self.start_time.strftime('%I:%M %p')} - {self.end_time.strftime('%I:%M %p')}"
        else:
            # Multiple days: "Oct 19, 2:30 PM - Oct 20, 5:45 PM"
            return f"{self.start_time.strftime('%b %d, %I:%M %p')} - {self.end_time.strftime('%b %d, %I:%M %p')}"

    @property
    def total_count(self) -> int:
        """Total media items in this event."""
        return len(self.items)


@dataclass
class DayGroup:
    """Collection of media items from a single calendar day."""

    # Identity
    date: datetime.date             # Calendar date (year, month, day)

    # Items
    items: list['LibraryItem']      # All media from this day (chronological order)
    best_shots: list['LibraryItem'] # Top-quality photos (5-10 items)

    # Statistics
    photo_count: int                # Number of photos
    video_count: int                # Number of videos

    # Events within the day (time-based clustering)
    events: list[EventCluster]      # Sub-groups within the day (optional)

    def __post_init__(self):
        """Validation and derived data."""
        assert len(self.items) > 0, "DayGroup must have at least one item"
        assert all(item.created_date.date() == self.date for item in self.items), \
            "All items must be from the same day"
        assert len(self.best_shots) <= 10, "Too many best shots (max 10)"
        # Ensure items are sorted chronologically
        self.items.sort(key=lambda x: x.created_date)

    @property
    def display_title(self) -> str:
        """Human-readable title for UI display."""
        return self.date.strftime("%A, %B %d, %Y")  # "Monday, October 19, 2025"

    @property
    def total_count(self) -> int:
        """Total media items in this day."""
        return len(self.items)


@dataclass
class MonthGroup:
    """Collection of media items from a single calendar month."""

    # Identity
    year: int                       # Year (e.g., 2025)
    month: int                      # Month (1-12)

    # Items
    items: list['LibraryItem']      # All media from this month (chronological order)
    events: list[EventCluster]      # Time-based event clusters

    # Day-level organization
    days: list[DayGroup]            # Days with photos (sparse - only days with content)

    # Statistics
    photo_count: int                # Number of photos
    video_count: int                # Number of videos
    day_count: int                  # Number of days with photos

    def __post_init__(self):
        """Validation and derived data."""
        assert 1 <= self.month <= 12, f"Invalid month: {self.month}"
        assert len(self.items) > 0, "MonthGroup must have at least one item"
        # Ensure items are sorted chronologically
        self.items.sort(key=lambda x: x.created_date)

    @property
    def display_title(self) -> str:
        """Human-readable title for UI display."""
        return datetime(self.year, self.month, 1).strftime("%B %Y")  # "October 2025"

    @property
    def total_count(self) -> int:
        """Total media items in this month."""
        return len(self.items)

    @property
    def date_range(self) -> tuple[datetime.date, datetime.date]:
        """First and last date with photos."""
        return (self.items[0].created_date.date(), self.items[-1].created_date.date())


@dataclass
class YearGroup:
    """Collection of media items from a single calendar year."""

    # Identity
    year: int                       # Year (e.g., 2025)

    # Items
    items: list['LibraryItem']      # All media from this year (chronological order)
    highlights: list['LibraryItem'] # Best photos (20-50 items, spread across year)

    # Month-level organization
    months: list[MonthGroup]        # Months with photos (sparse - only months with content)

    # Statistics
    photo_count: int                # Number of photos
    video_count: int                # Number of videos
    month_count: int                # Number of months with photos

    def __post_init__(self):
        """Validation and derived data."""
        assert len(self.items) > 0, "YearGroup must have at least one item"
        assert 20 <= len(self.highlights) <= 50, \
            f"Highlights count out of range (20-50): {len(self.highlights)}"
        # Ensure items are sorted chronologically
        self.items.sort(key=lambda x: x.created_date)

    @property
    def display_title(self) -> str:
        """Human-readable title for UI display."""
        return str(self.year)  # "2025"

    @property
    def total_count(self) -> int:
        """Total media items in this year."""
        return len(self.items)

    @property
    def date_range(self) -> tuple[datetime.date, datetime.date]:
        """First and last date with photos."""
        return (self.items[0].created_date.date(), self.items[-1].created_date.date())
