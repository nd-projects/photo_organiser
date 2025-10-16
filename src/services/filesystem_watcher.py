"""Filesystem watcher for detecting external changes to photos.

This module uses watchdog to monitor the photo directory for changes
(files added, removed, renamed) and notifies the UI to refresh.
Includes event debouncing to avoid excessive updates during bulk operations.
"""

import threading
import time
from pathlib import Path
from typing import Callable, List, Optional

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
except ImportError:
    Observer = None
    FileSystemEventHandler = None
    FileSystemEvent = None


class PhotoDirectoryHandler(FileSystemEventHandler):
    """File system event handler with debouncing.

    Collects filesystem events and batches them with a configurable
    debounce delay to avoid excessive callback invocations.
    """

    def __init__(self, callback: Callable[[List], None], debounce_ms: int = 500):
        """Initialize handler with callback and debounce delay.

        Args:
            callback: Function to call with batched events
            debounce_ms: Debounce delay in milliseconds (default 500ms)
        """
        super().__init__()
        self.callback = callback
        self.debounce_ms = debounce_ms
        self.pending_events: List[FileSystemEvent] = []
        self.timer: Optional[threading.Timer] = None
        self.lock = threading.Lock()

    def on_any_event(self, event: FileSystemEvent) -> None:
        """Handle any filesystem event.

        Args:
            event: Filesystem event from watchdog
        """
        # Ignore directory events for now, focus on files
        if event.is_directory:
            # But do handle directory creation/deletion (new albums)
            if event.event_type not in ['created', 'deleted', 'moved']:
                return

        with self.lock:
            # Add event to pending list
            self.pending_events.append(event)

            # Reset debounce timer
            if self.timer:
                self.timer.cancel()

            self.timer = threading.Timer(
                self.debounce_ms / 1000.0,
                self._process_events
            )
            self.timer.start()

    def _process_events(self) -> None:
        """Process batched events after debounce delay."""
        with self.lock:
            if not self.pending_events:
                return

            # Copy and clear pending events
            events = self.pending_events.copy()
            self.pending_events.clear()

            # Call callback with batched events
            try:
                self.callback(events)
            except Exception as e:
                print(f"Error in filesystem watcher callback: {e}")

    def stop(self) -> None:
        """Stop the handler and cancel any pending timers."""
        with self.lock:
            if self.timer:
                self.timer.cancel()
                self.timer = None
            self.pending_events.clear()


class FilesystemWatcher:
    """Filesystem watcher for photo directory changes.

    Monitors a directory tree for changes and notifies callbacks
    when photos are added, removed, or modified externally.
    """

    def __init__(self, root_dir: Path, callback: Callable[[List], None], debounce_ms: int = 500):
        """Initialize filesystem watcher.

        Args:
            root_dir: Root directory to watch
            callback: Function to call with batched events
            debounce_ms: Debounce delay in milliseconds

        Raises:
            ImportError: If watchdog is not available
            ValueError: If root_dir doesn't exist
        """
        if Observer is None or FileSystemEventHandler is None:
            raise ImportError("watchdog is required for filesystem watching")

        self.root_dir = Path(root_dir)

        if not self.root_dir.exists():
            raise ValueError(f"Root directory does not exist: {self.root_dir}")

        self.callback = callback
        self.debounce_ms = debounce_ms

        # Delay observer creation until start() is called
        self.observer: Optional[Observer] = None
        self.handler: Optional[PhotoDirectoryHandler] = None

        self._running = False

    def start(self) -> None:
        """Start watching the filesystem."""
        if not self._running:
            # Create observer and handler on first start
            if self.observer is None:
                self.observer = Observer()
                self.handler = PhotoDirectoryHandler(self.callback, self.debounce_ms)

                # Schedule watching
                self.observer.schedule(
                    self.handler,
                    str(self.root_dir),
                    recursive=True
                )

            self.observer.start()
            self._running = True

    def stop(self) -> None:
        """Stop watching the filesystem."""
        if self._running:
            if self.observer:
                self.observer.stop()
            if self.handler:
                self.handler.stop()
            self._running = False

    def join(self, timeout: Optional[float] = None) -> None:
        """Wait for the watcher thread to finish.

        Args:
            timeout: Timeout in seconds, or None to wait indefinitely
        """
        if self._running and self.observer:
            self.observer.join(timeout)

    def is_running(self) -> bool:
        """Check if watcher is currently running.

        Returns:
            True if watcher is active
        """
        return self._running

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


def create_watcher(
    root_dir: Path,
    callback: Callable[[List], None],
    debounce_ms: int = 500
) -> FilesystemWatcher:
    """Create and start a filesystem watcher.

    Args:
        root_dir: Root directory to watch
        callback: Function to call with batched events
        debounce_ms: Debounce delay in milliseconds

    Returns:
        FilesystemWatcher instance (already started)
    """
    watcher = FilesystemWatcher(root_dir, callback, debounce_ms)
    watcher.start()
    return watcher
