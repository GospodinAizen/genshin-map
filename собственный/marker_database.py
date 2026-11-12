"""Validated marker catalogue and thread-safe SQLite progress storage."""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from threading import RLock


class MarkerDatabase:
    def __init__(self, json_path: str | Path, database_path: str | Path) -> None:
        self.json_path = Path(json_path).resolve()
        self.database_path = Path(database_path).resolve()
        if not self.json_path.is_file():
            raise FileNotFoundError(f"Marker catalogue not found: {self.json_path}")
        raw = json.loads(self.json_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("Marker catalogue must be a JSON array.")
        self.markers = []
        seen = set()
        for marker in raw:
            missing = {"id", "name", "type", "x", "y"} - marker.keys()
            if missing:
                raise ValueError(f"Marker missing fields: {', '.join(sorted(missing))}")
            marker_id = str(marker["id"])
            if marker_id in seen:
                raise ValueError(f"Duplicate marker id: {marker_id}")
            seen.add(marker_id)
            self.markers.append({
                **marker,
                "id": marker_id,
                "map_id": str(marker.get("map_id", "teyvat_surface")),
                "floor_id": str(marker.get("floor_id", "surface")),
                "floor_label": str(marker.get("floor_label", "Поверхность")),
                "tile_id": str(marker.get("tile_id", "mondstadt_01")),
                "x": float(marker["x"]),
                "y": float(marker["y"]),
            })
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self.connection = sqlite3.connect(self.database_path, check_same_thread=False)
        self.connection.execute("""CREATE TABLE IF NOT EXISTS progress (
            marker_id TEXT PRIMARY KEY, found INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        self.connection.commit()

    def get_markers(self, map_id: str | None = None, floor_id: str | None = None) -> list[dict]:
        selected = self.markers
        if map_id is not None:
            selected = [m for m in selected if m["map_id"] == map_id]
        if floor_id is not None:
            selected = [m for m in selected if m["floor_id"] == floor_id]
        return list(selected)

    def get_floors(self) -> list[tuple[str, str]]:
        floors = {}
        for marker in self.markers:
            floors.setdefault(marker["floor_id"], marker["floor_label"])
        return sorted(floors.items(), key=lambda item: (item[0] != "surface", item[0]))

    def get_found_ids(self) -> set[str]:
        with self._lock:
            rows = self.connection.execute("SELECT marker_id FROM progress WHERE found=1").fetchall()
        return {row[0] for row in rows}

    def set_found(self, marker_id: str, found: bool) -> None:
        with self._lock:
            self.connection.execute("""INSERT INTO progress(marker_id, found) VALUES (?, ?)
                ON CONFLICT(marker_id) DO UPDATE SET found=excluded.found,
                updated_at=CURRENT_TIMESTAMP""", (marker_id, int(found)))
            self.connection.commit()

    def toggle_found(self, marker_id: str) -> bool:
        value = marker_id not in self.get_found_ids()
        self.set_found(marker_id, value)
        return value

    def reset_progress(self, map_id: str | None = None) -> None:
        with self._lock:
            if map_id is None:
                self.connection.execute("DELETE FROM progress")
            else:
                ids = [m["id"] for m in self.markers if m["map_id"] == map_id]
                if ids:
                    self.connection.executemany(
                        "DELETE FROM progress WHERE marker_id=?", [(item,) for item in ids]
                    )
            self.connection.commit()

    def close(self) -> None:
        with self._lock:
            self.connection.close()
