"""Build a single full-world reference image and runtime markers from HoYoLAB tiles.

HoYoLAB's public-map metadata defines the exact transform:
world pixel = point + origin; zoom -4 scale = 1/16; tile index = floor(pixel / 4096).
At zoom -4 the Teyvat canvas is a 9x8 grid of 256px tiles.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np

TILE_SIZE = 256
ZOOM = -4
SCALE = 2 ** ZOOM
TILE_ID = "teyvat_world_zoom_minus4"


def build_runtime_assets(snapshot_dir: str | Path) -> dict:
    root = Path(snapshot_dir).resolve()
    meta = json.loads((root / "meta.json").read_text(encoding="utf-8"))
    normalized = json.loads((root / "markers.normalized.json").read_text(encoding="utf-8"))
    origin = meta["origin"]
    total = meta["totalSize"]
    width = math.ceil(total[0] * SCALE / TILE_SIZE) * TILE_SIZE
    height = math.ceil(total[1] * SCALE / TILE_SIZE) * TILE_SIZE
    cols, rows = width // TILE_SIZE, height // TILE_SIZE
    if cols <= 0 or rows <= 0 or cols > 64 or rows > 64:
        raise ValueError(f"Unexpected zoom -4 tile grid: {cols}x{rows}")

    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    loaded = 0
    for ty in range(rows):
        for tx in range(cols):
            path = root / "tiles" / f"{tx}_{ty}_N4.webp"
            if not path.is_file():
                continue
            tile = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if tile is None:
                continue
            if tile.shape[:2] != (TILE_SIZE, TILE_SIZE):
                tile = cv2.resize(tile, (TILE_SIZE, TILE_SIZE), interpolation=cv2.INTER_AREA)
            canvas[ty*TILE_SIZE:(ty+1)*TILE_SIZE,
                   tx*TILE_SIZE:(tx+1)*TILE_SIZE] = tile
            loaded += 1
    if loaded < 8:
        raise RuntimeError(f"Only {loaded} official zoom -4 tiles loaded; refusing to create an unreliable map reference.")

    references = root / "references"
    references.mkdir(parents=True, exist_ok=True)
    image_path = references / "teyvat_world_zoom_minus4.png"
    if not cv2.imwrite(str(image_path), canvas):
        raise RuntimeError(f"Cannot write world reference image: {image_path}")
    manifest = {
        "monitor_index": 1,
        "tiles": [{"id": TILE_ID, "image": image_path.name, "neighbors": []}],
        "source": "HoYoLAB public interactive map",
        "source_map_id": meta["mapId"],
        "map_version": meta.get("mapVersion"),
        "reference_zoom": ZOOM,
    }
    (references / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    runtime_markers = []
    for marker in normalized["markers"]:
        if marker.get("z") not in (None, 0, "0"):
            continue
        x = (float(marker["map_x"]) + float(origin[0])) * SCALE
        y = (float(marker["map_y"]) + float(origin[1])) * SCALE
        if not (0 <= x < width and 0 <= y < height):
            continue
        category = marker.get("category_path") or ["Other"]
        runtime_markers.append({
            "id": marker["id"],
            "name": marker["name"],
            "type": str(category[0]),
            "category_path": category,
            "x": x,
            "y": y,
            "tile_id": TILE_ID,
            "map_id": "teyvat_surface",
            "source_point_id": marker.get("source_point_id"),
            "icon": marker.get("icon"),
        })
    if len(runtime_markers) < 1000:
        raise RuntimeError(f"Only {len(runtime_markers)} surface markers fit the official map bounds.")
    marker_path = root / "markers.runtime.json"
    marker_path.write_text(
        json.dumps(runtime_markers, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return {
        "reference_image": str(image_path),
        "manifest": str(references / "manifest.json"),
        "markers": str(marker_path),
        "tiles_loaded": loaded,
        "tiles_expected": cols * rows,
        "markers": len(runtime_markers),
        "reference_size": [width, height],
        "zoom": ZOOM,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot_dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(build_runtime_assets(args.snapshot_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
