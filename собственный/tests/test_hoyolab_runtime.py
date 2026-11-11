from __future__ import annotations

import json

import cv2
import numpy as np

from hoyolab_runtime import TILE_ID, build_runtime_assets
from reference_manager import ReferenceManager


def test_builds_official_world_reference_and_runtime_markers(tmp_path):
    root = tmp_path
    (root / "tiles").mkdir()
    meta = {
        "mapId": 2,
        "mapVersion": "test-version",
        "origin": [160, 320],
        "totalSize": [32768, 32768],
    }
    (root / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    # Eight zoom -4 tiles satisfy the minimum coverage guard. Use textured
    # tiles so ORB can index the stitched reference as the real tracker will.
    rng = np.random.default_rng(7)
    for tx, ty in [(x, y) for y in range(2) for x in range(4)]:
        tile = rng.integers(0, 256, (256, 256, 3), dtype=np.uint8)
        assert cv2.imwrite(str(root / "tiles" / f"{tx}_{ty}_N4.webp"), tile)

    markers = []
    for index in range(1200):
        markers.append({
            "id": f"hoyolab:2:surface:{index}",
            "name": "Test marker",
            "category_path": ["Resources", "Ore"],
            "map_x": 1000 + index,
            "map_y": 2000 + index,
            "z": 0,
            "source_point_id": str(index),
        })
    normalized = {"markers": markers}
    (root / "markers.normalized.json").write_text(
        json.dumps(normalized), encoding="utf-8"
    )

    result = build_runtime_assets(root)
    runtime = json.loads((root / "markers.runtime.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "references" / "manifest.json").read_text(encoding="utf-8"))

    assert result["tiles_loaded"] == 8
    assert result["markers"] == 1200
    assert runtime[0]["tile_id"] == TILE_ID
    assert runtime[0]["x"] == (1000 + 160) / 16
    assert runtime[0]["y"] == (2000 + 320) / 16
    assert manifest["tiles"][0]["id"] == TILE_ID

    manager = ReferenceManager(root / "references" / "manifest.json")
    assert TILE_ID in manager.tiles
