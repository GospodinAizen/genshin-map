from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QPen, QFont

from marker_renderer import prepare_markers, marker_color


class Overlay(QWidget):
    def __init__(self, database):
        super().__init__()
        self.database = database
        self.markers = []
        self.detection = None
        self.enabled_categories = {
            "chest", "oculus", "quest", "puzzle", "resource", "challenge"
        }
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        screen = QApplication.primaryScreen()
        if screen is not None:
            self.setGeometry(screen.geometry())
        self.hide()

    def toggle(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self._refresh()

    def set_category_enabled(self, category, enabled):
        if enabled:
            self.enabled_categories.add(category)
        else:
            self.enabled_categories.discard(category)
        self._refresh()

    def update_detection(self, detection):
        self.detection = detection
        self._refresh()

    def update_markers(self, detection):
        # Backwards-compatible name used by older entry points.
        self.update_detection(detection)

    def _refresh(self):
        self.markers = prepare_markers(
            self.database.get_markers(), self.detection,
            self.database, self.enabled_categories,
        )
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for marker in self.markers:
            color = marker_color(marker["type"])
            painter.setPen(QPen(QColor(*color), 2))
            painter.setBrush(QColor(*color))
            x, y = marker["x"], marker["y"]
            painter.drawEllipse(x - 7, y - 7, 14, 14)
            painter.setFont(QFont("Arial", 9))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(x + 11, y + 4, marker["name"])
