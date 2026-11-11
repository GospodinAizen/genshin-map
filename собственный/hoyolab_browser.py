"""Browse imported official-map markers and persist found progress.

This is the first user-testable HoYoLAB data client. It deliberately does not
project map coordinates onto the live game until that transform is verified.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QVBoxLayout,
    QWidget,
)

PAGE_SIZE = 100


class MarkerBrowser(QMainWindow):
    def __init__(self, snapshot: Path, progress_db: Path) -> None:
        super().__init__()
        payload = json.loads(snapshot.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("markers"), list):
            raise ValueError("Ожидается markers.normalized.json из загрузчика HoYoLAB.")
        self.markers = payload["markers"]
        self.source = payload.get("source", {})
        self.progress_db = progress_db
        self.progress_db.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.progress_db)
        self.db.execute("""CREATE TABLE IF NOT EXISTS found (
            marker_id TEXT PRIMARY KEY, found INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        self.db.commit()
        self.page = 0
        self.filtered = []
        self._loading = False

        self.setWindowTitle("Genshin Map — HoYoLAB markers")
        self.resize(780, 680)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        version = self.source.get("game_version", "неизвестна")
        layout.addWidget(QLabel(
            f"Источник: публичная интерактивная карта HoYoLAB · версия игры {version} · "
            f"точек в снимке: {len(self.markers):,}"
        ))
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск по названию категории…")
        self.search.textChanged.connect(self.apply_filters)
        filters.addWidget(self.search, 1)
        self.category = QComboBox()
        self.category.addItem("Все категории", None)
        categories = sorted({"/".join(m.get("category_path", [])) for m in self.markers})
        for item in categories:
            self.category.addItem(item, item)
        self.category.currentIndexChanged.connect(self.apply_filters)
        filters.addWidget(self.category, 2)
        layout.addLayout(filters)

        self.status = QLabel()
        layout.addWidget(self.status)
        self.items = QListWidget()
        self.items.itemChanged.connect(self.toggle_found)
        layout.addWidget(self.items, 1)

        controls = QHBoxLayout()
        self.prev = QPushButton("← Назад")
        self.prev.clicked.connect(self.previous_page)
        controls.addWidget(self.prev)
        self.page_label = QLabel()
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controls.addWidget(self.page_label, 1)
        self.next = QPushButton("Далее →")
        self.next.clicked.connect(self.next_page)
        controls.addWidget(self.next)
        layout.addLayout(controls)

        footer = QLabel(
            "Отметь найденные объекты галочками — прогресс сохраняется локально. "
            "Это проверка данных и учёта прогресса; привязка меток к экрану игры "
            "пока не включена."
        )
        footer.setWordWrap(True)
        layout.addWidget(footer)
        self.apply_filters()

    def found_ids(self) -> set[str]:
        return {row[0] for row in self.db.execute(
            "SELECT marker_id FROM found WHERE found=1"
        ).fetchall()}

    def apply_filters(self, *_args) -> None:
        query = self.search.text().strip().casefold()
        category = self.category.currentData()
        self.filtered = [
            marker for marker in self.markers
            if (not category or "/".join(marker.get("category_path", [])) == category)
            and (not query or query in (
                str(marker.get("name", "")) + " " +
                " ".join(marker.get("category_path", [])) + " " +
                str(marker.get("source_point_id", ""))
            ).casefold())
        ]
        self.page = 0
        self.render_page()

    def render_page(self) -> None:
        self._loading = True
        self.items.clear()
        start = self.page * PAGE_SIZE
        found = self.found_ids()
        for marker in self.filtered[start:start + PAGE_SIZE]:
            path = " / ".join(marker.get("category_path", []))
            item = QListWidgetItem(f'{marker.get("name", "—")}    ·    {path}')
            item.setData(Qt.ItemDataRole.UserRole, marker["id"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if marker["id"] in found
                else Qt.CheckState.Unchecked
            )
            self.items.addItem(item)
        total_pages = max(1, (len(self.filtered) + PAGE_SIZE - 1) // PAGE_SIZE)
        self.page_label.setText(f"Страница {self.page + 1} из {total_pages}")
        self.prev.setEnabled(self.page > 0)
        self.next.setEnabled(self.page + 1 < total_pages)
        self.status.setText(
            f"Найдено: {len(self.filtered):,} · отмечено найденными: {len(found):,}"
        )
        self._loading = False

    def toggle_found(self, item: QListWidgetItem) -> None:
        if self._loading:
            return
        marker_id = item.data(Qt.ItemDataRole.UserRole)
        value = int(item.checkState() == Qt.CheckState.Checked)
        self.db.execute(
            """INSERT INTO found(marker_id, found) VALUES (?, ?)
               ON CONFLICT(marker_id) DO UPDATE SET
               found=excluded.found, updated_at=CURRENT_TIMESTAMP""",
            (marker_id, value),
        )
        self.db.commit()
        self.status.setText(
            f"Найдено: {len(self.filtered):,} · отмечено найденными: {len(self.found_ids()):,}"
        )

    def previous_page(self) -> None:
        self.page = max(0, self.page - 1)
        self.render_page()

    def next_page(self) -> None:
        self.page += 1
        self.render_page()

    def closeEvent(self, event) -> None:
        self.db.close()
        event.accept()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--progress-db", type=Path, default=Path("data/hoyolab-progress.db"))
    args = parser.parse_args()
    if not args.snapshot.is_file():
        print(f"Не найден файл снимка: {args.snapshot}", file=sys.stderr)
        return 2
    app = QApplication(sys.argv)
    try:
        window = MarkerBrowser(args.snapshot, args.progress_db)
        window.show()
        return app.exec()
    except Exception as exc:
        QMessageBox.critical(None, "Genshin Map", str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
