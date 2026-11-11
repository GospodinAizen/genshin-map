"""Background screen-analysis worker with deterministic shutdown."""
from __future__ import annotations
import logging
from pathlib import Path
from PySide6.QtCore import QObject, QTimer, Signal, Slot, QThread
from screen_tracker import ScreenTracker

LOG = logging.getLogger(__name__)


class DetectionWorker(QObject):
    detection_ready = Signal(object)
    error = Signal(str)
    stop_requested = Signal()

    def __init__(self, manifest_path: str | Path, interval_ms: int = 350) -> None:
        super().__init__()
        self.manifest_path = Path(manifest_path)
        self.interval_ms = max(100, int(interval_ms))
        self.timer = None
        self.tracker = None
        self.stop_requested.connect(self.stop)

    @Slot()
    def start(self) -> None:
        try:
            self.tracker = ScreenTracker(self.manifest_path)
        except Exception as exc:
            LOG.exception("Tracker initialization failed")
            self.error.emit(str(exc))
            return
        self.timer = QTimer(self)
        self.timer.setInterval(self.interval_ms)
        self.timer.timeout.connect(self.detect_once)
        self.timer.start()
        self.detect_once()

    @Slot()
    def detect_once(self) -> None:
        if self.tracker is None:
            return
        try:
            self.detection_ready.emit(self.tracker.detect())
        except Exception as exc:
            LOG.exception("Screen detection failed")
            self.error.emit(str(exc))

    @Slot()
    def stop(self) -> None:
        if self.timer is not None:
            self.timer.stop()
            self.timer.deleteLater()
            self.timer = None
        if self.tracker is not None:
            self.tracker.close()
            self.tracker = None
        # Quit this worker's event loop only after resources have been released.
        QThread.currentThread().quit()
