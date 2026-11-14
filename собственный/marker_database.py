"""Validated marker catalogue and persistent found-state storage."""
from __future__ import annotations

import json
import math
import os
import sqlite3


class MarkerDatabase:
    def __init__(self, json_path: str):
        self.json_path = os.path.abspath(json_path)
        if not os.path.isfile(self.json_path):
            raise FileNotFoundError(f"Не найдена база объектов: {self.json_path}")

        with open(self.json_path, "r", encoding="utf-8") as file:
            markers = json.load(file)
        if not isinstance(markers, list):
            raise ValueError("База объектов должна быть JSON-списком")

        seen_ids = set()
        for index, marker in enumerate(markers):
            if not isinstance(marker, dict):
                raise ValueError(f"Метка #{index + 1} должна быть объектом")
            for field in ("id", "name", "type", "x", "y"):
                if field not in marker:
                    raise ValueError(f"В метке #{index + 1} отсутствует поле {field}")
            marker_id = str(marker["id"]).strip()
            if not marker_id or marker_id in seen_ids:
                raise ValueError(f"Пустой или повторяющийся id метки: {marker_id!r}")
            seen_ids.add(marker_id)
            marker["id"] = marker_id
            try:
                marker["x"], marker["y"] = float(marker["x"]), float(marker["y"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Некорректные координаты метки {marker_id}") from exc
            if not math.isfinite(marker["x"]) or not math.isfinite(marker["y"]):
                raise ValueError(f"Неконечные координаты метки {marker_id}")
            marker["name"] = str(marker["name"])
            marker["type"] = str(marker["type"])
            marker.setdefault("tile_id", "default")

        self.markers = markers
        data_dir = os.path.join(os.path.dirname(self.json_path), "data")
        os.makedirs(data_dir, exist_ok=True)
        self.connection = sqlite3.connect(os.path.join(data_dir, "progress.db"))
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS progress (
                marker_id TEXT PRIMARY KEY,
                found INTEGER NOT NULL DEFAULT 0 CHECK(found IN (0, 1))
            )
        """)
        self.connection.commit()

    def get_markers(self):
        return self.markers

    def get_found_ids(self) -> set[str]:
        rows = self.connection.execute(
            "SELECT marker_id FROM progress WHERE found = 1"
        ).fetchall()
        return {row[0] for row in rows}

    def is_found(self, marker_id) -> bool:
        return str(marker_id) in self.get_found_ids()

    def set_found(self, marker_id, found: bool) -> None:
        self.connection.execute("""
            INSERT INTO progress (marker_id, found) VALUES (?, ?)
            ON CONFLICT(marker_id) DO UPDATE SET found = excluded.found
        """, (str(marker_id), int(bool(found))))
        self.connection.commit()

    def toggle_found(self, marker_id) -> None:
        self.set_found(marker_id, not self.is_found(marker_id))

    def reset_progress(self) -> None:
        self.connection.execute("DELETE FROM progress")
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()
