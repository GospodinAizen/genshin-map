"""Background screen-analysis worker; keeps CV work off the Qt GUI thread."""
from __future__ import annotations
import logging
from pathlib import Path
from PySide6.QtCore import QObject, QTimer, Signal, Slot
from screen_tracker import ScreenTracker

LOG = logging.getLogger(__name__)


class DetectionWorker(QObject):
    detection_ready = Signal(object)
    error = Signal(str)

    def __init__(self, manifest_path: str | Path, interval_ms: int = 350) -> None:
        super().__init__()
        self.manifest_path = Path(manifest_path)
        self.interval_ms = max(100, int(interval_ms))
        self.timer = None
        self.tracker = None

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
        if self.tracker is not None:
            self.tracker.close()
            self.tracker = None
