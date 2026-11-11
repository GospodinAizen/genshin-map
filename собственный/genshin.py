import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from overlay import Overlay
from screen_tracker import ScreenTracker
from marker_database import MarkerDatabase
from hotkeys import HotkeyListener


def main():
    app = QApplication(sys.argv)

    database = MarkerDatabase("data/markers.json")
    tracker = ScreenTracker("data/map_reference.png")
    overlay = Overlay(database)

    timer = QTimer()
    timer.timeout.connect(
        lambda: overlay.update_markers(tracker.detect())
    )
    timer.start(300)

    hotkeys = HotkeyListener(overlay.toggle)
    hotkeys.start()

    overlay.show()

    exit_code = app.exec()

    hotkeys.stop()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()






