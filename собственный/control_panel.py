"""Control window for category filters and found/unfound marker progress."""
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QVBoxLayout, QMessageBox,
)
from marker_renderer import COLORS

CATEGORY_NAMES = {
    "chest": "Сундуки", "oculus": "Окулусы", "quest": "Задания",
    "puzzle": "Загадки", "resource": "Ресурсы", "challenge": "Испытания",
}


class ControlPanel(QDialog):
    toggle_requested = Signal()

    def __init__(self, database, overlay):
        super().__init__()
        self.database = database
        self.overlay = overlay
        self._loading = False
        self._tile_id = None
        self._found_snapshot = set()
        self.detection = None
        self.setWindowTitle("Genshin Map — управление метками")
        self.setMinimumWidth(340)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.toggle_requested.connect(self.toggle)

        root = QVBoxLayout(self)
        root.addWidget(QLabel("Категории меток"))
        self.category_checks = {}
        for category in COLORS:
            checkbox = QCheckBox(CATEGORY_NAMES.get(category, category))
            checkbox.setChecked(True)
            checkbox.toggled.connect(
                lambda enabled, kind=category:
                    self.overlay.set_category_enabled(kind, enabled)
            )
            self.category_checks[category] = checkbox
            root.addWidget(checkbox)

        root.addWidget(QLabel("Объекты текущего участка"))
        self.status_label = QLabel("Ожидание распознавания карты…")
        root.addWidget(self.status_label)
        self.marker_list = QListWidget()
        self.marker_list.itemChanged.connect(self._marker_changed)
        root.addWidget(self.marker_list)

        buttons = QHBoxLayout()
        self.reset_button = QPushButton("Сбросить прогресс")
        self.reset_button.clicked.connect(self._reset_progress)
        buttons.addWidget(self.reset_button)
        close_button = QPushButton("Скрыть")
        close_button.clicked.connect(self.hide)
        buttons.addWidget(close_button)
        root.addLayout(buttons)
        root.addWidget(QLabel("M — оверлей · F6 — панель"))

    @Slot(object)
    def update_detection(self, detection):
        self.detection = detection
        if detection is None:
            tile_id = "default"
            markers = [
                m for m in self.database.get_markers()
                if m.get("tile_id", "default") == tile_id
            ]
            self.status_label.setText(
                f"Распознавание недоступно · участок {tile_id} · "
                f"объектов: {len(markers)}"
            )
        else:
            tile_id = detection.get("tile_id", "default")
            markers = [
                m for m in self.database.get_markers()
                if m.get("tile_id", "default") == tile_id
            ]
            self.status_label.setText(
                f"Участок: {tile_id} · объектов: {len(markers)}"
            )
        found = self.database.get_found_ids()
        if tile_id == self._tile_id and found == self._found_snapshot:
            return
        self._loading = True
        try:
            self.marker_list.clear()
            for marker in markers:
                item = QListWidgetItem(
                    f'{marker["name"]}  [{marker["type"]}]'
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
        finally:
            self._loading = False
        return

    @Slot(QListWidgetItem)
    def _marker_changed(self, item):
        if self._loading:
            return
        self.database.set_found(
            item.data(Qt.ItemDataRole.UserRole),
            item.checkState() == Qt.CheckState.Checked,
        )
        self._found_snapshot = self.database.get_found_ids()
        self.overlay.update_detection(self.detection)

    @Slot()
    def _reset_progress(self):
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
        self._tile_id = None
        self.update_detection(self.detection)
        self.overlay.update_detection(self.detection)

    @Slot()
    def toggle(self):
        self.setVisible(not self.isVisible())

    @Slot(str)
    def show_error(self, message):
        self.status_label.setText(f"Ошибка распознавания: {message}")

    def closeEvent(self, event):
        event.ignore()
        self.hide()
