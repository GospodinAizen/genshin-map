"""Build a multiscale reference pyramid from the official HoYoLAB tile pyramid.

References are 3x3 tile mosaics at every published zoom level. Marker coordinates
remain in source map units; each detection carries the zoom scale and mosaic origin
needed to project them into the matched screenshot.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np

TILE_SIZE = 256
BLOCK_TILES = 3
LEGACY_TILE_ID = "teyvat_world_zoom_minus4"


def _suffix(zoom: int) -> str:
    return f"N{abs(zoom)}" if zoom < 0 else f"P{zoom}"


def build_runtime_assets(snapshot_dir: str | Path) -> dict:
    root = Path(snapshot_dir).resolve()
    meta = json.loads((root / "meta.json").read_text(encoding="utf-8"))
    normalized = json.loads((root / "markers.normalized.json").read_text(encoding="utf-8"))
    origin = meta["origin"]
    total = meta["totalSize"]
    min_zoom = int(meta.get("minZoom", -4))
    max_zoom = int(meta.get("maxZoom", 0))
    if min_zoom > max_zoom or min_zoom < -8 or max_zoom > 4:
        raise ValueError(f"Unsupported HoYoLAB zoom range: {min_zoom}..{max_zoom}")

    references = root / "references"
    references.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    loaded_by_zoom: dict[str, int] = {}
    generated = 0

    for zoom in range(min_zoom, max_zoom + 1):
        scale = 2 ** zoom
        cols = math.ceil(total[0] * scale / TILE_SIZE)
        rows = math.ceil(total[1] * scale / TILE_SIZE)
        blocks_x = math.ceil(cols / BLOCK_TILES)
        blocks_y = math.ceil(rows / BLOCK_TILES)
        loaded_tiles = 0
        for by in range(blocks_y):
            for bx in range(blocks_x):
                canvas = np.zeros(
                    (BLOCK_TILES * TILE_SIZE, BLOCK_TILES * TILE_SIZE, 3),
                    dtype=np.uint8,
                )
                loaded = 0
                for dy in range(BLOCK_TILES):
                    for dx in range(BLOCK_TILES):
                        tx, ty = bx * BLOCK_TILES + dx, by * BLOCK_TILES + dy
                        if tx >= cols or ty >= rows:
                            continue
                        tile_path = root / "tiles" / f"{tx}_{ty}_{_suffix(zoom)}.webp"
                        if not tile_path.is_file():
                            continue
                        tile = cv2.imread(str(tile_path), cv2.IMREAD_COLOR)
                        if tile is None:
                            continue
                        if tile.shape[:2] != (TILE_SIZE, TILE_SIZE):
                            tile = cv2.resize(tile, (TILE_SIZE, TILE_SIZE), interpolation=cv2.INTER_AREA)
                        y0, x0 = dy * TILE_SIZE, dx * TILE_SIZE
                        canvas[y0:y0 + TILE_SIZE, x0:x0 + TILE_SIZE] = tile
                        loaded += 1
                # Ignore empty and badly damaged mosaics; partial edge blocks are valid.
                expected = min(BLOCK_TILES, cols - bx * BLOCK_TILES) * min(BLOCK_TILES, rows - by * BLOCK_TILES)
                if loaded < max(3, math.ceil(expected * 0.55)):
                    continue
                tile_id = f"teyvat_z{zoom}_b{bx}_{by}"
                image_name = f"{tile_id}.jpg"
                image_path = references / image_name
                if not cv2.imwrite(str(image_path), canvas, [cv2.IMWRITE_JPEG_QUALITY, 94]):
                    raise RuntimeError(f"Cannot write reference mosaic: {image_path}")
                entries.append({
                    "id": tile_id,
                    "image": image_name,
                    "neighbors": [],
                    "reference_origin": [bx * BLOCK_TILES * TILE_SIZE, by * BLOCK_TILES * TILE_SIZE],
                    "reference_scale": scale,
                    "reference_zoom": zoom,
                })
                loaded_tiles += loaded
                generated += 1
        loaded_by_zoom[str(zoom)] = loaded_tiles

    if generated < 20:
        raise RuntimeError(
            f"Only {generated} usable multiscale reference mosaics were built; "
            "the downloaded map tile pyramid is incomplete."
        )

    # Link adjacent mosaics at the same zoom so tracking remains local after initial acquisition.
    by_key = {(e["reference_zoom"], e["id"].split("_b", 1)[1]): e for e in entries}
    for entry in entries:
        zoom = entry["reference_zoom"]
        bx = entry["reference_origin"][0] // (BLOCK_TILES * TILE_SIZE)
        by = entry["reference_origin"][1] // (BLOCK_TILES * TILE_SIZE)
        neighbors = []
        for ny in range(max(0, by - 1), by + 2):
            for nx in range(max(0, bx - 1), bx + 2):
                if nx == bx and ny == by:
                    continue
                neighbor_id = f"teyvat_z{zoom}_b{nx}_{ny}"
                if any(candidate["id"] == neighbor_id for candidate in entries):
                    neighbors.append(neighbor_id)
        entry["neighbors"] = neighbors

    manifest = {
        "monitor_index": 1,
        "tiles": entries,
        "source": "HoYoLAB public interactive map",
        "source_map_id": meta["mapId"],
        "map_version": meta.get("mapVersion"),
        "zoom_range": [min_zoom, max_zoom],
        "reference_mosaics": generated,
        "block_tiles": BLOCK_TILES,
    }
    (references / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    runtime_markers = []
    for marker in normalized["markers"]:
        if marker.get("z") not in (None, 0, "0"):
            continue
        map_x, map_y = float(marker["map_x"]), float(marker["map_y"])
        world_x, world_y = map_x + float(origin[0]), map_y + float(origin[1])
        runtime_markers.append({
            "id": marker["id"],
            "name": marker["name"],
            "type": str((marker.get("category_path") or ["Other"])[0]),
            "category_path": marker.get("category_path") or ["Other"],
            "x": map_x,
            "y": map_y,
            "world_x": world_x,
            "world_y": world_y,
            "tile_id": "teyvat_multiscale",
            "map_id": "teyvat_surface",
            "source_point_id": marker.get("source_point_id"),
            "icon": marker.get("icon"),
        })
    if len(runtime_markers) < 1000:
        raise RuntimeError(f"Only {len(runtime_markers)} surface markers were imported.")
    marker_path = root / "markers.runtime.json"
    marker_path.write_text(
        json.dumps(runtime_markers, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return {
        "manifest": str(references / "manifest.json"),
        "marker_file": str(marker_path),
        "tiles_loaded_by_zoom": loaded_by_zoom,
        "reference_mosaics": generated,
        "markers": len(runtime_markers),
        "zoom_range": [min_zoom, max_zoom],
        "block_tiles": BLOCK_TILES,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot_dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(build_runtime_assets(args.snapshot_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
