"""Transparent click-through marker layer. Settings and marker actions live in ControlPanel."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from marker_renderer import COLORS, marker_color, prepare_markers


class Overlay(QWidget):
    toggle_requested = Signal()

    def __init__(self, database) -> None:
        super().__init__()
        self.database = database
        self.markers: list[dict] = []
        self.detection: dict | None = None
        self.enabled_types = set(COLORS)
        self.toggle_requested.connect(self.toggle)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint |
                            Qt.WindowType.Tool |
                            Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.hide()

    @Slot()
    def toggle(self) -> None:
        self.setVisible(not self.isVisible())

    @Slot(object)
    def update_detection(self, detection) -> None:
        self.detection = detection
        if detection is None:
            self.markers = []
            self.update()
            return
        ox, oy = detection["monitor_origin"]
        width, height = detection["monitor_size"]
        self.setGeometry(ox, oy, width, height)
        self.markers = prepare_markers(self.database.get_markers(), detection,
                                       self.database.get_found_ids(), self.enabled_types)
        self.update()

    def set_category_enabled(self, category: str, enabled: bool) -> None:
        if enabled:
            self.enabled_types.add(category)
        else:
            self.enabled_types.discard(category)
        self.update_detection(self.detection)

    @Slot(str)
    def show_error(self, message: str) -> None:
        self.setToolTip(message)

    def paintEvent(self, event) -> None:
        if not self.markers:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        ox, oy = self.detection.get("monitor_origin", (0, 0)) if self.detection else (0, 0)
        for marker in self.markers:
            color = marker_color(marker["type"])
            x = round(marker["screen_x"] + ox - self.geometry().x())
            y = round(marker["screen_y"] + oy - self.geometry().y())
            painter.setPen(QPen(QColor(*color), 2))
            painter.setBrush(QColor(*color))
            painter.drawEllipse(x - 6, y - 6, 12, 12)
            painter.setFont(QFont("Arial", 9))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(x + 10, y + 4, str(marker["name"]))
