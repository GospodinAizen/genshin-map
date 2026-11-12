import json
import cv2
import numpy as np
from reference_manager import ReferenceManager


def test_neighbor_tiles_are_prioritized(tmp_path):
    tiles_dir = tmp_path / "tiles"
    tiles_dir.mkdir()
    rng = np.random.default_rng(42)
    for name in ("a.png", "b.png", "c.png"):
        image = rng.integers(0, 256, (320, 320), dtype=np.uint8)
        assert cv2.imwrite(str(tiles_dir / name), image)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "monitor_index": 1,
        "tiles": [
            {"id": "a", "image": "tiles/a.png", "neighbors": ["b"]},
            {"id": "b", "image": "tiles/b.png", "neighbors": ["a"]},
            {"id": "c", "image": "tiles/c.png", "neighbors": []}
        ]
    }), encoding="utf-8")
    manager = ReferenceManager(manifest, max_features=500, min_features=10)
    assert [tile.tile_id for tile in manager.candidates("a")] == ["a", "b"]
    assert [tile.tile_id for tile in manager.candidates(None)] == ["a", "b", "c"]
