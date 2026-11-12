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


def test_floor_layers_are_available_and_progress_is_shared(tmp_path):
    catalogue = tmp_path / "markers.json"
    catalogue.write_text(json.dumps([
        {"id": "surface", "name": "Chest", "type": "chest", "x": 10, "y": 20,
         "floor_id": "surface", "floor_label": "Поверхность"},
        {"id": "underground", "name": "Chest", "type": "chest", "x": 11, "y": 21,
         "floor_id": "z:-1", "floor_label": "Уровень -1"},
    ]), encoding="utf-8")
    db = MarkerDatabase(catalogue, tmp_path / "progress.db")
    try:
        assert db.get_floors() == [("surface", "Поверхность"), ("z:-1", "Уровень -1")]
        assert [m["id"] for m in db.get_markers(floor_id="z:-1")] == ["underground"]
        db.set_found("underground", True)
        assert db.get_found_ids() == {"underground"}
    finally:
        db.close()
