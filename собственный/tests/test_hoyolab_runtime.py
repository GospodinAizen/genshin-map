from __future__ import annotations

import json

import cv2
import numpy as np

from hoyolab_runtime import build_runtime_assets
from reference_manager import ReferenceManager


def test_builds_multiscale_reference_mosaics_and_runtime_markers(tmp_path):
    root = tmp_path
    tiles_dir = root / "tiles"
    tiles_dir.mkdir()
    meta = {
        "mapId": 2,
        "mapVersion": "test-version",
        "origin": [160, 320],
        "totalSize": [16384, 16384],
        "minZoom": -4,
        "maxZoom": -2,
    }
    (root / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    rng = np.random.default_rng(7)
    for zoom in range(-4, -1):
        scale = 2 ** zoom
        cols = int(meta["totalSize"][0] * scale / 256)
        rows = int(meta["totalSize"][1] * scale / 256)
        suffix = f"N{abs(zoom)}"
        for ty in range(rows):
            for tx in range(cols):
                tile = rng.integers(0, 256, (256, 256, 3), dtype=np.uint8)
                assert cv2.imwrite(str(tiles_dir / f"{tx}_{ty}_{suffix}.webp"), tile)

    markers = []
    for index in range(1200):
        markers.append({
            "id": f"hoyolab:2:surface:{index}",
            "name": "Test marker",
            "category_path": ["Resources", "Ore"],
            "map_x": 1000 + index,
            "map_y": 2000 + index,
            "z": 0 if index < 1198 else (-1 if index == 1198 else 1),
            "source_point_id": str(index),
        })
    (root / "markers.normalized.json").write_text(
        json.dumps({"markers": markers}), encoding="utf-8"
    )

    result = build_runtime_assets(root)
    runtime = json.loads((root / "markers.runtime.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "references" / "manifest.json").read_text(encoding="utf-8"))

    assert result["reference_mosaics"] == 21
    assert result["markers"] == 1200
    assert result["markers_by_floor"] == {"surface": 1198, "z:-1": 1, "z:1": 1}
    assert runtime[0]["tile_id"] == "teyvat_surface_multiscale"
    assert runtime[0]["x"] == 1000
    assert runtime[0]["y"] == 2000
    assert runtime[-2]["floor_id"] == "z:-1"
    assert runtime[-1]["floor_label"] == "Уровень 1"
    assert runtime[0]["world_x"] == 1160
    assert manifest["zoom_range"] == [-4, -2]
    assert manifest["reference_mosaics"] == 21

    manager = ReferenceManager(root / "references" / "manifest.json", max_features=100)
    assert len(manager.tiles) == 21
    assert any(tile.reference_scale == 0.25 for tile in manager.tiles.values())
    assert any(tile.reference_scale == 0.0625 for tile in manager.tiles.values())
