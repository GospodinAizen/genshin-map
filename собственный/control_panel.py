"""Control window for category filters, floor selection and progress."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout, QScrollArea,
    QWidget, QProgressBar,
)
from localization import display_name
from marker_renderer import prepare_markers
from map_viewer import MapViewer


class ControlPanel(QDialog):
    toggle_requested = Signal()

    def __init__(self, database, overlay, map_root=None) -> None:
        super().__init__()
        self.database = database
        self.overlay = overlay
        self.map_root = map_root
        self.map_viewer = None
        self._loading = False
        self._tile_id = None
        self._floor_id = "surface"
        self._found_snapshot: set[str] = set()
        self._visible_marker_ids: tuple[str, ...] = ()
        self.detection = None
        self.setWindowTitle("Genshin Map — управление метками")
        self.setMinimumWidth(370)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.toggle_requested.connect(self.toggle)

        root = QVBoxLayout(self)
        self.open_map_button = QPushButton("Открыть подробную карту")
        self.open_map_button.setEnabled(map_root is not None and (map_root / "meta.json").is_file())
        self.open_map_button.clicked.connect(self._open_map)
        root.addWidget(self.open_map_button)

        root.addWidget(QLabel("Определение этажа"))
        self.floor_combo = QComboBox()
        self.floor_combo.addItem("Авто: поверхность", "auto")
        for floor_id, floor_label in database.get_floors():
            self.floor_combo.addItem(f"Вручную: {floor_label}", floor_id)
        self.floor_combo.currentIndexChanged.connect(self._floor_changed)
        root.addWidget(self.floor_combo)
        self.floor_hint = QLabel("Авто выбирает поверхность; подземные карты пока требуют ручного выбора.")
        self.floor_hint.setWordWrap(True)
        self.floor_hint.setStyleSheet("color: #999;")
        root.addWidget(self.floor_hint)

        root.addWidget(QLabel("Прогресс исследования"))
        self.progress_label = QLabel()
        root.addWidget(self.progress_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        root.addWidget(self.progress_bar)
        self._refresh_progress()

        root.addWidget(QLabel("Категории меток"))
        self.category_checks = {}
        category_scroll = QScrollArea()
        category_scroll.setWidgetResizable(True)
        category_scroll.setMaximumHeight(220)
        category_widget = QWidget()
        category_layout = QVBoxLayout(category_widget)
        categories = sorted({str(m.get("type", "Other")) for m in database.markers})
        for category in categories:
            checkbox = QCheckBox(display_name(category))
            checkbox.setChecked(True)
            checkbox.toggled.connect(
                lambda enabled, kind=category: self.overlay.set_category_enabled(kind, enabled)
            )
            self.category_checks[category] = checkbox
            category_layout.addWidget(checkbox)
        category_layout.addStretch(1)
        category_scroll.setWidget(category_widget)
        root.addWidget(category_scroll)

        root.addWidget(QLabel("Объекты текущего участка"))
        self.status_label = QLabel(f"База загружена: {len(database.markers)} меток. Ожидание распознавания…")
        self.status_label.setWordWrap(True)
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
        help_text = QLabel("M — оверлей · F6 — панель · F7 — клики по меткам\nЛКМ — найдено · ПКМ — вернуть метку")
        help_text.setStyleSheet("color: #888;")
        root.addWidget(help_text)

    @Slot()
    def _open_map(self) -> None:
        if self.map_root is None:
            return
        if self.map_viewer is None:
            self.map_viewer = MapViewer(self.map_root)
        self.map_viewer.show()
        self.map_viewer.raise_()
        self.map_viewer.activateWindow()

    def _refresh_progress(self) -> None:
        total = len(self.database.markers)
        found = len(self.database.get_found_ids() & {m["id"] for m in self.database.markers})
        percent = round(found * 100 / total) if total else 0
        self.progress_label.setText(f"Отмечено найденным: {found:,} из {total:,} ({percent}%)")
        self.progress_bar.setValue(percent)

    @Slot(object)
    def update_detection(self, detection) -> None:
        self.detection = detection
        if detection is None:
            self._tile_id = None
            self._found_snapshot = set()
            self._visible_marker_ids = ()
            self.status_label.setText(
                f"Карта не распознана. В базе {len(self.database.markers):,} меток. "
                "Откройте полноэкранную игровую карту; проверьте монитор и масштаб интерфейса."
            )
            self.marker_list.clear()
            return
        tile_id = detection["tile_id"]
        all_types = {str(m.get("type", "Other")) for m in self.database.markers}
        markers = prepare_markers(self.database.get_markers(floor_id=self._floor_id), detection, set(), all_types)
        found = self.database.get_found_ids()
        zoom = detection.get("reference_zoom", "?")
        confidence = detection.get("confidence", 0.0)
        self.status_label.setText(
            f"Распознано: {tile_id} · масштаб {zoom} · уверенность {confidence:.0%} · "
            f"маркеров на экране: {len(markers):,}. Слой: {self._floor_id}"
        )
        visible_ids = tuple(marker["id"] for marker in markers[:1000])
        if (tile_id == self._tile_id and self._floor_id == getattr(self, "_rendered_floor_id", None)
                and found == self._found_snapshot and visible_ids == self._visible_marker_ids):
            return
        self._loading = True
        self.marker_list.clear()
        for marker in markers[:1000]:
            item = QListWidgetItem(f'{display_name(marker["name"])}  [{display_name(marker["type"])}]')
            item.setData(Qt.ItemDataRole.UserRole, marker["id"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if marker["id"] in found else Qt.CheckState.Unchecked)
            self.marker_list.addItem(item)
        self._tile_id = tile_id
        self._rendered_floor_id = self._floor_id
        self._found_snapshot = found
        self._visible_marker_ids = visible_ids
        self._loading = False
        self._refresh_progress()

    @Slot(int)
    def _floor_changed(self, index: int) -> None:
        selected = self.floor_combo.itemData(index)
        self._floor_id = "surface" if selected == "auto" else str(selected)
        self.overlay.set_floor(self._floor_id)
        self.floor_hint.setText(
            "Автоматически выбран слой «Поверхность». Автоопределение подземных помещений "
            "появится после добавления отдельных эталонных изображений этажей."
            if selected == "auto" else
            "Ручной слой включён. Это фильтр меток по z-уровню, а не отдельная подземная карта."
        )
        self._tile_id = None
        self.update_detection(self.detection)

    @Slot(QListWidgetItem)
    def _marker_changed(self, item: QListWidgetItem) -> None:
        if self._loading:
            return
        self.database.set_found(item.data(Qt.ItemDataRole.UserRole),
                                item.checkState() == Qt.CheckState.Checked)
        self._found_snapshot = self.database.get_found_ids()
        self._refresh_progress()
        if self.detection is not None:
            self.overlay.update_detection(self.detection)

    @Slot()
    def _reset_progress(self) -> None:
        answer = QMessageBox.question(
            self, "Сброс прогресса", "Снять отметку «найдено» со всех объектов?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.database.reset_progress()
        self._found_snapshot = set()
        self._refresh_progress()
        self.update_detection(self.detection)
        self.overlay.update_detection(self.detection)

    @Slot()
    def toggle(self) -> None:
        self.setVisible(not self.isVisible())

    @Slot(str)
    def show_status(self, message: str) -> None:
        if self.detection is None:
            self.status_label.setText(message)

    @Slot(str)
    def show_error(self, message: str) -> None:
        self.status_label.setText(f"ОШИБКА: {message}")

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()
