"""
Asynchronous thumbnail loader using QThreadPool for background generation.

This module provides non-blocking thumbnail loading using Qt's thread pool,
allowing the UI to remain responsive during thumbnail generation.
"""

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class WorkerSignals(QObject):
    """
    Signals for communicating between worker thread and main thread.

    Qt signals must be defined on a QObject, not on QRunnable directly.
    """
    # Emitted when thumbnail successfully loaded/generated
    # Parameters: (index: int, thumbnail_path: Path)
    thumbnail_ready = pyqtSignal(int, Path)

    # Emitted when thumbnail loading/generation failed
    # Parameters: (index: int, error_message: str)
    thumbnail_failed = pyqtSignal(int, str)


class ThumbnailWorker(QRunnable):
    """
    Background worker for thumbnail generation/loading.

    This worker checks the cache first (with mtime validation), then generates
    a new thumbnail if needed. Runs in a background thread from QThreadPool.
    """

    def __init__(
        self,
        index: int,
        source_path: Path,
        size: tuple[int, int],
        photo_processor,
        thumbnail_cache
    ):
        """
        Initialize thumbnail worker.

        Args:
            index: Model index for this thumbnail
            source_path: Path to source image file
            size: Desired thumbnail size (width, height)
            photo_processor: PhotoProcessor instance for generating thumbnails
            thumbnail_cache: ThumbnailCache instance for caching
        """
        super().__init__()
        self.signals = WorkerSignals()
        self.index = index
        self.source_path = source_path
        self.size = size
        self.photo_processor = photo_processor
        self.thumbnail_cache = thumbnail_cache

    @pyqtSlot()
    def run(self):
        """
        Execute in background thread.

        Checks cache first (with mtime validation), generates new thumbnail if needed,
        and emits signals when complete or on error.
        """
        try:
            # Check cache first (mtime validation done inside cache.get())
            cached = self.thumbnail_cache.get(self.source_path, self.size)
            if cached and cached.exists():
                logger.debug(f"Cache hit for {self.source_path.name}")
                self.signals.thumbnail_ready.emit(self.index, cached)
                return

            # Generate new thumbnail
            logger.debug(f"Generating thumbnail for {self.source_path.name}")
            thumbnail_path = self.photo_processor.generate_thumbnail(
                self.source_path,
                self.size
            )

            if thumbnail_path and thumbnail_path.exists():
                self.signals.thumbnail_ready.emit(self.index, thumbnail_path)
            else:
                self.signals.thumbnail_failed.emit(
                    self.index,
                    "Thumbnail generation returned None or invalid path"
                )

        except Exception as e:
            logger.error(f"Failed to load thumbnail for {self.source_path}: {e}")
            self.signals.thumbnail_failed.emit(self.index, str(e))


class ThumbnailLoader:
    """
    Manages asynchronous thumbnail loading using QThreadPool.

    This class coordinates thumbnail generation/loading in background threads,
    allowing the UI to remain responsive. Uses Qt's global thread pool for
    efficient resource management.
    """

    def __init__(self, photo_processor, thumbnail_cache):
        """
        Initialize thumbnail loader.

        Args:
            photo_processor: PhotoProcessor instance for generating thumbnails
            thumbnail_cache: ThumbnailCache instance for caching
        """
        self.thread_pool = QThreadPool.globalInstance()
        self.photo_processor = photo_processor
        self.thumbnail_cache = thumbnail_cache

        # Log thread pool configuration
        max_threads = self.thread_pool.maxThreadCount()
        logger.info(f"ThumbnailLoader initialized (max {max_threads} threads)")

    def queue_thumbnail(
        self,
        index: int,
        source_path: Path,
        size: tuple[int, int],
        priority: int = 0
    ) -> ThumbnailWorker:
        """
        Queue a thumbnail for asynchronous loading/generation.

        Args:
            index: Model index for this thumbnail (used in signals)
            source_path: Path to source image file
            size: Desired thumbnail size (width, height)
            priority: Worker priority (0 = high/visible, 1 = low/pre-cache)

        Returns:
            ThumbnailWorker instance (caller should connect signals)

        Note:
            The caller must connect to worker.signals.thumbnail_ready and
            worker.signals.thumbnail_failed before calling this method.
        """
        worker = ThumbnailWorker(
            index,
            source_path,
            size,
            self.photo_processor,
            self.thumbnail_cache
        )

        # Start worker in thread pool
        # Note: QThreadPool uses priority inversely (lower number = higher priority)
        self.thread_pool.start(worker, priority)

        return worker

    def queue_batch(
        self,
        requests: list[tuple[int, Path, tuple[int, int], int]]
    ) -> list[ThumbnailWorker]:
        """
        Queue multiple thumbnails for batch loading.

        Args:
            requests: List of (index, source_path, size, priority) tuples

        Returns:
            List of ThumbnailWorker instances (caller should connect signals)
        """
        workers = []
        for index, source_path, size, priority in requests:
            worker = self.queue_thumbnail(index, source_path, size, priority)
            workers.append(worker)

        logger.debug(f"Queued {len(requests)} thumbnails for loading")
        return workers

    def clear_queue(self):
        """
        Clear pending thumbnail tasks.

        Note: This will clear ALL tasks in the global thread pool, not just
        thumbnail tasks. Use with caution if other components use the thread pool.
        """
        self.thread_pool.clear()
        logger.info("Thumbnail queue cleared")

    def active_thread_count(self) -> int:
        """
        Get number of currently active threads.

        Returns:
            Number of active threads in the thread pool
        """
        return self.thread_pool.activeThreadCount()

    def max_thread_count(self) -> int:
        """
        Get maximum number of threads in the pool.

        Returns:
            Maximum thread count
        """
        return self.thread_pool.maxThreadCount()
