"""Application entry point. All paths are resolved relative to this file."""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication, QMessageBox

from control_panel import ControlPanel
from hotkeys import HotkeyListener
from marker_database import MarkerDatabase
from overlay import Overlay
from screen_tracker import ScreenTracker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MARKERS_PATH = os.path.join(BASE_DIR, "marker.json")
REFERENCE_PATH = os.path.join(BASE_DIR, "data", "map_reference.png")


class DetectionWorker(QObject):
    detected = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, reference_path):
        super().__init__()
        self.reference_path = reference_path
        self.tracker = None
        self.timer = None

    @Slot()
    def start(self):
        try:
            self.tracker = ScreenTracker(self.reference_path)
            self.timer = QTimer(self)
            self.timer.timeout.connect(self._detect)
            self.timer.start(500)
        except Exception as exc:
            self.failed.emit(str(exc))
            self.finished.emit()

    @Slot()
    def _detect(self):
        try:
            self.detected.emit(self.tracker.detect())
        except Exception as exc:
            self.failed.emit(str(exc))
            if self.timer is not None:
                self.timer.stop()
            self.finished.emit()

    @Slot()
    def stop(self):
        if self.timer is not None:
            self.timer.stop()
        if self.tracker is not None:
            self.tracker.close()
            self.tracker = None
        self.finished.emit()


class HotkeySignals(QObject):
    toggle_overlay = Signal()
    toggle_panel = Signal()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Genshin Map Overlay")

    try:
        database = MarkerDatabase(MARKERS_PATH)
    except (OSError, ValueError, TypeError) as exc:
        QMessageBox.critical(None, "Ошибка базы меток", str(exc))
        return 1

    overlay = Overlay(database)
    panel = ControlPanel(database, overlay)
    overlay.hide()
    panel.show()

    thread = QThread()
    worker = None
    if os.path.isfile(REFERENCE_PATH):
        worker = DetectionWorker(REFERENCE_PATH)
        worker.moveToThread(thread)
        thread.started.connect(worker.start)
        worker.detected.connect(overlay.update_detection)
        worker.detected.connect(panel.update_detection)
        worker.failed.connect(panel.show_error)
        worker.finished.connect(thread.quit)
        thread.start()
    else:
        panel.status_label.setText(
            "База меток загружена. Нет data/map_reference.png — "
            "распознавание экрана отключено."
        )

    signals = HotkeySignals()
    signals.toggle_overlay.connect(overlay.toggle)
    signals.toggle_panel.connect(panel.toggle)
    hotkeys = HotkeyListener(
        signals.toggle_overlay.emit, signals.toggle_panel.emit
    )
    try:
        hotkeys.start()
    except Exception as exc:
        panel.show_error(f"Не удалось включить глобальные клавиши: {exc}")

    def shutdown():
        hotkeys.stop()
        if worker is not None and thread.isRunning():
            worker.stop()
            thread.quit()
            thread.wait(3000)
        overlay.close()
        panel.close()
        database.close()

    app.aboutToQuit.connect(shutdown)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
