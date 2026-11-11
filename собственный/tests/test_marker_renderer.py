import numpy as np

from marker_renderer import prepare_markers


def test_prepare_markers_projects_and_culls_to_viewport():
    markers = [
        {"id": "visible", "tile_id": "world", "map_id": "teyvat_surface",
         "type": "Exploration", "x": 30, "y": 40, "name": "Visible"},
        {"id": "outside", "tile_id": "world", "map_id": "teyvat_surface",
         "type": "Exploration", "x": 500, "y": 500, "name": "Outside"},
        {"id": "found", "tile_id": "world", "map_id": "teyvat_surface",
         "type": "Exploration", "x": 50, "y": 60, "name": "Found"},
        {"id": "wrong-type", "tile_id": "world", "map_id": "teyvat_surface",
         "type": "Resources", "x": 50, "y": 60, "name": "Wrong type"},
        {"id": "wrong-map", "tile_id": "other", "map_id": "teyvat_surface",
         "type": "Exploration", "x": 50, "y": 60, "name": "Wrong tile"},
    ]
    detection = {
        "tile_id": "world",
        "homography": np.eye(3, dtype=np.float32),
        "screen_size": (100, 100),
        "map_id": "teyvat_surface",
    }
    result = prepare_markers(
        markers, detection, {"found"}, {"Exploration"}
    )
    assert [marker["id"] for marker in result] == ["visible"]
    assert result[0]["screen_x"] == 30
    assert result[0]["screen_y"] == 40


def test_prepare_markers_returns_empty_without_detection_or_candidates():
    marker = {"id": "a", "tile_id": "world", "type": "Exploration", "x": 1, "y": 2}
    assert prepare_markers([marker], None, set(), {"Exploration"}) == []
    assert prepare_markers([marker], {"tile_id": "elsewhere"}, set(), {"Exploration"}) == []
