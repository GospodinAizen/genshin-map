"""Application entry point and lifetime management."""
from __future__ import annotations
import logging
import sys
from pathlib import Path
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication, QMessageBox
from control_panel import ControlPanel
from hotkeys import HotkeyListener
from marker_database import MarkerDatabase
from overlay import Overlay
from worker import DetectionWorker

ROOT = Path(__file__).resolve().parent


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    app = QApplication(sys.argv)
    app.setApplicationName("Genshin Map Overlay")
    database = None
    thread = None
    worker = None
    hotkeys = None
    try:
        database = MarkerDatabase(ROOT / "marker.json", ROOT / "data" / "progress.db")
        overlay = Overlay(database)
        panel = ControlPanel(database, overlay)
        panel.show()

        thread = QThread()
        worker = DetectionWorker(ROOT / "references" / "manifest.json", interval_ms=350)
        worker.moveToThread(thread)
        thread.started.connect(worker.start)
        worker.detection_ready.connect(overlay.update_detection)
        worker.detection_ready.connect(panel.update_detection)
        worker.error.connect(overlay.show_error)
        worker.error.connect(panel.show_error)
        app.aboutToQuit.connect(worker.stop_requested.emit)
        thread.finished.connect(worker.deleteLater)
        thread.start()

        hotkeys = HotkeyListener(overlay.toggle_requested.emit, panel.toggle_requested.emit,\n                                overlay.interaction_requested.emit)
        hotkeys.start()
        logging.getLogger(__name__).info("M: overlay · F6: controls · F7: marker click mode.")
        return app.exec()
    except Exception as exc:
        logging.getLogger(__name__).exception("Application startup failed")
        QMessageBox.critical(None, "Genshin Map Overlay", str(exc))
        return 1
    finally:
        if hotkeys is not None:
            hotkeys.stop()
        if worker is not None and thread is not None and thread.isRunning():
            worker.stop_requested.emit()
            thread.wait(5000)
        if database is not None:
            database.close()


if __name__ == "__main__":
    raise SystemExit(main())
