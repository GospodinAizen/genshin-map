"""Control window for category filters and marker progress."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, Slot
from localization import display_name

from PySide6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QVBoxLayout,
)


class ControlPanel(QDialog):
    toggle_requested = Signal()

    def __init__(self, database, overlay) -> None:
        super().__init__()
        self.database = database
        self.overlay = overlay
        self._loading = False
        self._tile_id = None
        self._found_snapshot: set[str] = set()
        self.detection = None
        self.setWindowTitle("Genshin Map — управление метками")
        self.setMinimumWidth(340)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.toggle_requested.connect(self.toggle)

        root = QVBoxLayout(self)
        root.addWidget(QLabel("Категории меток"))
        self.category_checks = {}
        categories = sorted({str(m.get("type", "Other")) for m in database.markers})
        for category in categories:
            checkbox = QCheckBox(display_name(category))
            checkbox.setChecked(True)
            checkbox.toggled.connect(
                lambda enabled, kind=category: self.overlay.set_category_enabled(kind, enabled)
            )
            self.category_checks[category] = checkbox
            root.addWidget(checkbox)

        root.addWidget(QLabel("Объекты текущего участка"))
        self.status_label = QLabel(
            f"Загружено меток: {len(database.markers)}. Ожидание распознавания карты…"
        )
        root.addWidget(self.status_label)
        self.marker_list = QListWidget()
        self.marker_list.itemChanged.connect(self._marker_changed)
        root.addWidget(self.marker_list)

        buttons = QHBoxLayout()
        reset_button = QPushButton("Сбросить прогресс")
        reset_button.clicked.connect(self._reset_progress)
        buttons.addWidget(reset_button)
        hide_button = QPushButton("Скрыть")
        hide_button.clicked.connect(self.hide)
        buttons.addWidget(hide_button)
        root.addLayout(buttons)

        help_text = QLabel(
            "M — оверлей · F6 — панель · F7 — клики по меткам\n"
            "ЛКМ — найдено · ПКМ — вернуть метку\n"
            "Метки и названия загружены из публичной карты HoYoLAB"
        )
        help_text.setStyleSheet("color: #888;")
        root.addWidget(help_text)

    @Slot(object)
    def update_detection(self, detection) -> None:
        self.detection = detection
        if detection is None:
            self._tile_id = None
            self._found_snapshot = set()
            self.status_label.setText(
                f"Карта не распознана · в базе {len(self.database.markers)} меток. "
                "Проверьте, открыта ли игровая карта"
            )
            self.marker_list.clear()
            return

        tile_id = detection["tile_id"]
        markers = list(self.overlay.markers)
        found = self.database.get_found_ids()
        shown = min(len(markers), 1000)
        suffix = f" · показаны первые {shown}" if len(markers) > shown else ""
        zoom = detection.get("reference_zoom", "?")
        confidence = detection.get("confidence", 0.0)
        self.status_label.setText(
            f"Карта распознана · масштаб {zoom} · уверенность {confidence:.0%} · "
            f"видимых объектов: {len(markers)}{suffix}"
        )

        # Keep selection and scroll position; refresh only on tile/progress changes.
        if tile_id == self._tile_id and found == self._found_snapshot:
            return

        self._loading = True
        self.marker_list.clear()
        for marker in markers[:1000]:
            item = QListWidgetItem(
                f'{display_name(marker["name"])}  [{display_name(marker["type"])}]'
            )
            item.setData(Qt.ItemDataRole.UserRole, marker["id"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if marker["id"] in found
                else Qt.CheckState.Unchecked
            )
            self.marker_list.addItem(item)
        self._tile_id = tile_id
        self._found_snapshot = found
        self._loading = False

    @Slot(QListWidgetItem)
    def _marker_changed(self, item: QListWidgetItem) -> None:
        if self._loading:
            return
        marker_id = item.data(Qt.ItemDataRole.UserRole)
        self.database.set_found(
            marker_id, item.checkState() == Qt.CheckState.Checked
        )
        self._found_snapshot = self.database.get_found_ids()
        if self.detection is not None:
            self.overlay.update_detection(self.detection)

    @Slot()
    def _reset_progress(self) -> None:
        answer = QMessageBox.question(
            self, "Сброс прогресса",
            "Снять отметку «найдено» со всех объектов?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.database.reset_progress()
        self._found_snapshot = set()
        self.update_detection(self.detection)
        self.overlay.update_detection(self.detection)

    @Slot()
    def toggle(self) -> None:
        self.setVisible(not self.isVisible())

    @Slot(str)
    def show_error(self, message: str) -> None:
        self.status_label.setText(f"Ошибка: {message}")

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()
