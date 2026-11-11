import json
import os
import sqlite3


class MarkerDatabase:
    def __init__(self, json_path):
        self.json_path = json_path

        if not os.path.exists(json_path):
            raise FileNotFoundError(
                f"Не найдена база объектов: {json_path}"
            )

        with open(
            json_path,
            "r",
            encoding="utf-8"
        ) as file:
            self.markers = json.load(file)

        os.makedirs("data", exist_ok=True)

        self.connection = sqlite3.connect(
            "data/progress.db"
        )

        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS progress (
                marker_id TEXT PRIMARY KEY,
                found INTEGER DEFAULT 0
            )
        """)

        self.connection.commit()

    def get_markers(self):
        return self.markers

    def is_found(self, marker_id):
        result = self.connection.execute(
            "SELECT found FROM progress WHERE marker_id = ?",
            (marker_id,)
        ).fetchone()

        return bool(result[0]) if result else False

    def toggle_found(self, marker_id):
        current = self.is_found(marker_id)

        self.connection.execute("""
            INSERT INTO progress (marker_id, found)
            VALUES (?, ?)
            ON CONFLICT(marker_id)
            DO UPDATE SET found = excluded.found
        """, (marker_id, int(not current)))

        self.connection.commit()

    def close(self):
        self.connection.close()