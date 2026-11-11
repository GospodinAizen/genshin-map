import json
import pytest

from hoyolab_importer import flatten_labels, import_snapshot


def write_snapshot(root, *, labels=None, points=None):
    root.mkdir()
    (root / "meta.json").write_text(json.dumps({
        "mapId": 2, "mapVersion": "abc", "gameVersion": "7.2.0",
        "origin": [0, 0], "totalSize": [1000, 800],
        "minZoom": -2, "maxZoom": 4, "fetchedAt": "2026-11-09T00:00:00Z",
    }), encoding="utf-8")
    (root / "labels.json").write_text(json.dumps(labels or [
        {"id": 10, "name": "Exploration", "icon": "icons/a.webp", "children": [
            {"id": 11, "name": "Common Chest", "icon": "icons/b.webp"}
        ]}
    ]), encoding="utf-8")
    (root / "points.json").write_text(json.dumps(points or [
        {"id": 123, "labelId": 11, "x": 12.5, "y": 42.25, "z": 2},
    ]), encoding="utf-8")


def test_import_preserves_official_identity_hierarchy_and_coordinates(tmp_path):
    source = tmp_path / "snapshot"
    write_snapshot(source)
    result = import_snapshot(source)
    marker = result["markers"][0]
    assert marker["id"] == "hoyolab:2:2:123"
    assert marker["source_point_id"] == "123"
    assert marker["label_id"] == "11"
    assert marker["name"] == "Common Chest"
    assert marker["category_path"] == ["Exploration", "Common Chest"]
    assert marker["map_x"] == 12.5
    assert marker["map_y"] == 42.25
    assert marker["z"] == 2
    assert marker["coordinate_space"] == "hoyolab_map"
    assert result["source"]["map_version"] == "abc"


def test_import_skips_points_with_unknown_label_without_fabricating_category(tmp_path):
    source = tmp_path / "snapshot"
    write_snapshot(source, points=[
        {"id": 1, "labelId": 999, "x": 1, "y": 2},
    ])
    result = import_snapshot(source)
    assert result["markers"] == []
    assert result["skipped_unknown_labels"] == 1


def test_duplicate_label_ids_are_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        flatten_labels([
            {"id": 1, "name": "A"},
            {"id": 1, "name": "B"},
        ])


def test_duplicate_point_ids_are_rejected(tmp_path):
    source = tmp_path / "snapshot"
    write_snapshot(source, points=[
        {"id": 7, "labelId": 11, "x": 1, "y": 2},
        {"id": 7, "labelId": 11, "x": 3, "y": 4},
    ])
    with pytest.raises(ValueError, match="Duplicate"):
        import_snapshot(source)
