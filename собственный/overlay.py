"""Transparent overlay with optional marker-only mouse interaction."""
from __future__ import annotations
import math
from collections import defaultdict
from PySide6.QtCore import Qt, Signal, Slot, QRect
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QRegion
from PySide6.QtWidgets import QWidget
from localization import display_name
from marker_renderer import COLORS, marker_color, prepare_markers


class Overlay(QWidget):
    toggle_requested = Signal()
    interaction_requested = Signal()

    def __init__(self, database) -> None:
        super().__init__()
        self.database = database
        self.markers: list[dict] = []
        self.detection: dict | None = None
        self.enabled_types = {str(marker.get('type', 'Other')) for marker in database.markers}
        self.interactive = False
        self.toggle_requested.connect(self.toggle)
        self.interaction_requested.connect(self.toggle_interaction)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._apply_window_flags()
        self.hide()

    def _apply_window_flags(self) -> None:
        was_visible = self.isVisible()
        flags = (Qt.WindowType.FramelessWindowHint |
                 Qt.WindowType.WindowStaysOnTopHint |
                 Qt.WindowType.Tool)
        if not self.interactive:
            flags |= Qt.WindowType.WindowTransparentForInput
        self.setWindowFlags(flags)
        if was_visible:
            self.show()
            self.raise_()

    @Slot()
    def toggle(self) -> None:
        self.setVisible(not self.isVisible())

    @Slot()
    def toggle_interaction(self) -> None:
        self.interactive = not self.interactive
        self._apply_window_flags()
        self._update_hit_region()
        self.setToolTip(
            "Клики по меткам включены: ЛКМ — найдено, ПКМ — не найдено"
            if self.interactive else "Режим сквозных кликов включён"
        )

    @Slot(object)
    def update_detection(self, detection) -> None:
        self.detection = detection
        if detection is None:
            self.markers = []
            self.clearMask()
            self.update()
            return
        ox, oy = detection["monitor_origin"]
        width, height = detection["monitor_size"]
        self.setGeometry(ox, oy, width, height)
        self.markers = prepare_markers(self.database.get_markers(), detection,
                                       self.database.get_found_ids(), self.enabled_types)
        self._update_hit_region()
        self.update()

    def _marker_rect(self, marker: dict) -> QRect:
        ox, oy = self.detection.get("monitor_origin", (0, 0))
        x = round(marker["screen_x"] + ox - self.geometry().x())
        y = round(marker["screen_y"] + oy - self.geometry().y())
        label_width = min(260, max(42, len(str(marker["name"])) * 8))
        return QRect(x - 13, y - 13, label_width + 28, 27)

    def _update_hit_region(self) -> None:
        if not self.interactive:
            self.clearMask()
            return
        if len(self.markers) > 5000:
            # At overview zoom a click target per marker would create a huge
            # native region. Restore click-through so the game never gets blocked.
            self.interactive = False
            self._apply_window_flags()
            self.clearMask()
            self.setToolTip("Слишком много меток для режима кликов. Приблизь карту или используй F6.")
            return
        region = QRegion()
        for marker in self.markers:
            region = region.united(QRegion(self._marker_rect(marker)))
        self.setMask(region)

    def set_category_enabled(self, category: str, enabled: bool) -> None:
        if enabled:
            self.enabled_types.add(category)
        else:
            self.enabled_types.discard(category)
        self.update_detection(self.detection)

    def mousePressEvent(self, event) -> None:
        if not self.interactive or self.detection is None:
            event.ignore()
            return
        point = event.position().toPoint()
        for marker in self.markers:
            if self._marker_rect(marker).contains(point):
                self.database.set_found(
                    marker["id"], event.button() != Qt.MouseButton.RightButton
                )
                self.update_detection(self.detection)
                event.accept()
                return
        event.ignore()

    @Slot(str)
    def show_error(self, message: str) -> None:
        self.setToolTip(message)

    def paintEvent(self, event) -> None:
        if not self.markers:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        ox, oy = self.detection.get("monitor_origin", (0, 0)) if self.detection else (0, 0)

        if len(self.markers) > 1500:
            # Cluster the full-world overview instead of drawing tens of
            # thousands of overlapping text labels.
            clusters = defaultdict(list)
            for marker in self.markers:
                x = marker["screen_x"] + ox - self.geometry().x()
                y = marker["screen_y"] + oy - self.geometry().y()
                clusters[(marker["type"], round(x / 12), round(y / 12))].append((x, y))
            for (category, _gx, _gy), points in clusters.items():
                x = round(sum(p[0] for p in points) / len(points))
                y = round(sum(p[1] for p in points) / len(points))
                color = QColor(*marker_color(category))
                radius = min(9, 3 + int(math.sqrt(len(points))))
                painter.setPen(QPen(color, 1))
                painter.setBrush(color)
                painter.drawEllipse(x - radius, y - radius, radius * 2, radius * 2)
                if len(points) >= 5:
                    painter.setPen(QColor(255, 255, 255))
                    painter.setFont(QFont("Arial", 8))
                    painter.drawText(x + radius, y, str(len(points)))
            return

        for marker in self.markers:
            color = marker_color(marker["type"])
            x = round(marker["screen_x"] + ox - self.geometry().x())
            y = round(marker["screen_y"] + oy - self.geometry().y())
            painter.setPen(QPen(QColor(*color), 2))
            painter.setBrush(QColor(*color))
            painter.drawEllipse(x - 6, y - 6, 12, 12)
            painter.setFont(QFont("Arial", 9))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(x + 10, y + 4, display_name(marker["name"]))
