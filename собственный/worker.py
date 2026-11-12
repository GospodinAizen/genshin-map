"""Background screen-analysis worker with visible diagnostic status."""
from __future__ import annotations
import logging
from pathlib import Path
from PySide6.QtCore import QObject, QTimer, Signal, Slot, QThread
from screen_tracker import ScreenTracker

LOG = logging.getLogger(__name__)


class DetectionWorker(QObject):
    detection_ready = Signal(object)
    error = Signal(str)
    status = Signal(str)
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
            self.status.emit(f"Загрузка эталонов карты: {self.manifest_path}")
            self.tracker = ScreenTracker(self.manifest_path)
            self.status.emit(self.tracker.last_status)
        except Exception as exc:
            LOG.exception("Tracker initialization failed")
            self.error.emit(f"Не удалось загрузить эталоны: {exc}")
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
            detection = self.tracker.detect()
            self.detection_ready.emit(detection)
            self.status.emit(self.tracker.last_status)
        except Exception as exc:
            LOG.exception("Screen detection failed")
            self.error.emit(f"Ошибка анализа экрана: {exc}")

    @Slot()
    def stop(self) -> None:
        if self.timer is not None:
            self.timer.stop()
            self.timer.deleteLater()
            self.timer = None
        if self.tracker is not None:
            self.tracker.close()
            self.tracker = None
        QThread.currentThread().quit()
