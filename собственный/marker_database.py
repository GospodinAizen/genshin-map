"""Validated marker catalogue and persistent found-state storage."""
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
            self.markers.append({**marker, "id": marker_id,
                                 "tile_id": str(marker.get("tile_id", "mondstadt_01")),
                                 "x": float(marker["x"]), "y": float(marker["y"])})
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self.connection = sqlite3.connect(self.database_path, check_same_thread=False)
        self.connection.execute("""CREATE TABLE IF NOT EXISTS progress (
            marker_id TEXT PRIMARY KEY, found INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        self.connection.commit()

    def get_markers(self) -> list[dict]:
        return list(self.markers)

    def get_found_ids(self) -> set[str]:
        with self._lock:
            rows = self.connection.execute("SELECT marker_id FROM progress WHERE found = 1").fetchall()
        return {row[0] for row in rows}

    def is_found(self, marker_id: str) -> bool:
        with self._lock:
            row = self.connection.execute("SELECT found FROM progress WHERE marker_id = ?",
                                          (marker_id,)).fetchone()
        return bool(row and row[0])

    def toggle_found(self, marker_id: str) -> bool:
        with self._lock:
            new_value = not self.is_found(marker_id)
            self.connection.execute("""INSERT INTO progress(marker_id, found) VALUES (?, ?)
                ON CONFLICT(marker_id) DO UPDATE SET found=excluded.found,
                updated_at=CURRENT_TIMESTAMP""", (marker_id, int(new_value)))
            self.connection.commit()
        return new_value

    def close(self) -> None:
        with self._lock:
            self.connection.close()
