import json
import os
import tempfile
import unittest

from marker_database import MarkerDatabase


class MarkerDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = os.path.join(self.temp.name, "markers.json")
        with open(self.path, "w", encoding="utf-8") as stream:
            json.dump([
                {"id": "a", "name": "Chest", "type": "chest", "x": 1, "y": 2}
            ], stream)

    def test_progress_persists_and_can_be_reset(self):
        db = MarkerDatabase(self.path)
        self.addCleanup(db.close)
        self.assertEqual(db.get_found_ids(), set())
        db.set_found("a", True)
        self.assertEqual(db.get_found_ids(), {"a"})
        db.set_found("a", False)
        self.assertEqual(db.get_found_ids(), set())
        db.set_found("a", True)
        db.reset_progress()
        self.assertEqual(db.get_found_ids(), set())

    def test_default_tile_is_added(self):
        db = MarkerDatabase(self.path)
        self.addCleanup(db.close)
        self.assertEqual(db.get_markers()[0]["tile_id"], "default")

    def test_duplicate_ids_are_rejected(self):
        with open(self.path, "w", encoding="utf-8") as stream:
            json.dump([
                {"id": "x", "name": "A", "type": "chest", "x": 1, "y": 2},
                {"id": "x", "name": "B", "type": "chest", "x": 3, "y": 4},
            ], stream)
        with self.assertRaisesRegex(ValueError, "повторяющийся"):
            MarkerDatabase(self.path)

    def test_non_finite_coordinates_are_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                with open(self.path, "w", encoding="utf-8") as stream:
                    json.dump([
                        {"id": "x", "name": "A", "type": "chest", "x": value, "y": 2}
                    ], stream)
                with self.assertRaisesRegex(ValueError, "Неконечные"):
                    MarkerDatabase(self.path)


if __name__ == "__main__":
    unittest.main()
