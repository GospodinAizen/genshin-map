import json
from marker_database import MarkerDatabase


def test_progress_round_trip_and_reset(tmp_path):
    catalogue = tmp_path / "markers.json"
    catalogue.write_text(json.dumps([
        {"id": "a", "name": "Chest", "type": "chest", "tile_id": "tile-a", "x": 10, "y": 20}
    ]), encoding="utf-8")
    db = MarkerDatabase(catalogue, tmp_path / "data" / "progress.db")
    try:
        assert db.get_found_ids() == set()
        db.set_found("a", True)
        assert db.get_found_ids() == {"a"}
        assert db.toggle_found("a") is False
        assert db.get_found_ids() == set()
        db.set_found("a", True)
        db.reset_progress()
        assert db.get_found_ids() == set()
    finally:
        db.close()
