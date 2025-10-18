#!/usr/bin/env python3
"""Performance profiling script for photo organizer.

This script profiles key performance metrics for virtual scrolling with 500+ albums.
"""

import sys
import time
import cProfile
import pstats
import io
from pathlib import Path
from datetime import datetime, date
import tempfile
import shutil
import random

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

from src.models.album import Album
from src.ui.album_grid import AlbumGrid


def create_test_albums(count: int, temp_dir: Path) -> list[Album]:
    """Create test albums for performance testing.

    Args:
        count: Number of albums to create
        temp_dir: Temporary directory for test data

    Returns:
        List of test Album objects
    """
    albums = []

    for i in range(count):
        # Create album directory
        album_name = f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}_Album_{i:04d}"
        album_path = temp_dir / album_name
        album_path.mkdir(exist_ok=True)

        # Create a test thumbnail
        thumbnail_path = temp_dir / "thumbnails" / f"thumb_{i}.jpg"
        thumbnail_path.parent.mkdir(exist_ok=True, parents=True)

        # Create a simple test image (just create file, not actual image)
        thumbnail_path.touch()

        # Create album object
        album = Album(
            path=album_path,
            name=album_name,
            date=date(2024, random.randint(1, 12), random.randint(1, 28)),
            photo_count=random.randint(10, 500),
            thumbnail_path=thumbnail_path,
            photos=[]
        )

        albums.append(album)

    return albums


def profile_album_grid_initialization(album_count: int):
    """Profile AlbumGrid initialization with many albums.

    Args:
        album_count: Number of albums to test with
    """
    print(f"\n{'='*70}")
    print(f"Profiling AlbumGrid with {album_count} albums")
    print(f"{'='*70}\n")

    # Create Qt application
    app = QApplication(sys.argv)

    # Create temporary directory for test data
    temp_dir = Path(tempfile.mkdtemp(prefix="photo_organiser_profile_"))

    try:
        # Create test albums
        print(f"Creating {album_count} test albums...")
        start = time.perf_counter()
        albums = create_test_albums(album_count, temp_dir)
        elapsed = time.perf_counter() - start
        print(f"✓ Created {album_count} albums in {elapsed:.3f}s\n")

        # Profile grid initialization
        print("Profiling grid widget creation...")
        start = time.perf_counter()
        grid = AlbumGrid(enable_drag_drop=True)
        elapsed = time.perf_counter() - start
        print(f"✓ Grid created in {elapsed:.3f}s")

        # Profile set_albums
        print(f"\nProfiling set_albums({album_count})...")

        profiler = cProfile.Profile()
        profiler.enable()

        start = time.perf_counter()
        grid.set_albums(albums)
        elapsed = time.perf_counter() - start

        profiler.disable()

        print(f"✓ set_albums() completed in {elapsed:.3f}s")

        # Show profiler results
        print("\n" + "-"*70)
        print("Top 20 time-consuming functions:")
        print("-"*70)

        s = io.StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
        ps.print_stats(20)
        print(s.getvalue())

        # Test scrolling performance
        print("\n" + "-"*70)
        print("Testing scroll performance...")
        print("-"*70)

        grid.show()

        # Measure time to scroll to bottom
        start = time.perf_counter()
        grid.list_widget.scrollToBottom()
        app.processEvents()  # Process paint events
        elapsed_scroll_down = time.perf_counter() - start
        print(f"✓ Scroll to bottom: {elapsed_scroll_down:.3f}s")

        # Measure time to scroll to top
        start = time.perf_counter()
        grid.list_widget.scrollToTop()
        app.processEvents()  # Process paint events
        elapsed_scroll_up = time.perf_counter() - start
        print(f"✓ Scroll to top: {elapsed_scroll_up:.3f}s")

        # Test item access performance
        print("\n" + "-"*70)
        print("Testing item access performance...")
        print("-"*70)

        start = time.perf_counter()
        for i in range(0, album_count, 10):  # Sample every 10th item
            item = grid.list_widget.item(i)
            album = item.data(1)  # Qt.UserRole = 1
        elapsed = time.perf_counter() - start
        print(f"✓ Accessed {album_count // 10} items in {elapsed:.3f}s")

        # Memory usage estimate
        print("\n" + "-"*70)
        print("Memory estimates:")
        print("-"*70)

        grid_size = sys.getsizeof(grid)
        items_size = grid.list_widget.count() * sys.getsizeof(grid.list_widget.item(0))
        albums_size = sum(sys.getsizeof(a) for a in albums)

        print(f"Grid widget: ~{grid_size / 1024:.1f} KB")
        print(f"List items: ~{items_size / 1024:.1f} KB")
        print(f"Album objects: ~{albums_size / 1024:.1f} KB")
        print(f"Total estimated: ~{(grid_size + items_size + albums_size) / 1024:.1f} KB")

        # Performance summary
        print("\n" + "="*70)
        print("PERFORMANCE SUMMARY")
        print("="*70)
        print(f"Album count: {album_count}")
        print(f"Grid initialization: {elapsed:.3f}s")
        print(f"Scroll to bottom: {elapsed_scroll_down:.3f}s")
        print(f"Scroll to top: {elapsed_scroll_up:.3f}s")

        # Check against requirements
        target_startup = 2.0  # seconds
        if elapsed > target_startup:
            print(f"\n⚠ WARNING: Grid initialization ({elapsed:.3f}s) exceeds target ({target_startup}s)")
        else:
            print(f"\n✓ PASS: Grid initialization within target ({target_startup}s)")

        grid.close()

    finally:
        # Cleanup
        print("\n" + "-"*70)
        print("Cleaning up...")
        shutil.rmtree(temp_dir)
        print("✓ Cleanup complete")

        app.quit()


def main():
    """Main entry point."""
    print("Photo Organizer Performance Profiler")
    print("="*70)

    # Test with different album counts
    test_sizes = [100, 250, 500, 750, 1000]

    for size in test_sizes:
        profile_album_grid_initialization(size)
        print("\n\n")


if __name__ == "__main__":
    main()
