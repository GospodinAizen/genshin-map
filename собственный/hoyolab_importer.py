"""Import a HoYoLAB map snapshot into a lossless, normalized marker catalogue.

Expected input files are the public-map snapshot format:
  meta.json, labels.json, points.json
The importer never invents marker names or coordinates. It preserves source IDs,
label hierarchy, map coordinates, z-levels, icon paths, and attribution metadata.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read valid JSON from {path}: {exc}") from exc


def flatten_labels(nodes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index nested label tree while retaining its full category path."""
    result: dict[str, dict[str, Any]] = {}

    def visit(items: list[dict[str, Any]], parents: tuple[str, ...]) -> None:
        for node in items:
            if not isinstance(node, dict) or "id" not in node or "name" not in node:
                raise ValueError("Every label node must contain id and name.")
            label_id = str(node["id"])
            if label_id in result:
                raise ValueError(f"Duplicate HoYoLAB label id: {label_id}")
            name = str(node["name"])
            path = (*parents, name)
            result[label_id] = {
                "id": label_id,
                "name": name,
                "path": list(path),
                "icon": node.get("icon"),
            }
            children = node.get("children") or []
            if not isinstance(children, list):
                raise ValueError(f"Label children must be an array: {label_id}")
            visit(children, path)

    visit(nodes, ())
    return result


def import_snapshot(input_dir: str | Path, *, map_key: str | None = None) -> dict[str, Any]:
    root = Path(input_dir)
    meta = _read_json(root / "meta.json")
    labels_raw = _read_json(root / "labels.json")
    points_raw = _read_json(root / "points.json")
    if not isinstance(meta, dict) or not isinstance(labels_raw, list) or not isinstance(points_raw, list):
        raise ValueError("meta.json must be an object; labels.json and points.json must be arrays.")
    if meta.get("mapId") is None:
        raise ValueError("meta.json is missing mapId.")

    source_map_id = str(meta["mapId"])
    map_id = str(map_key or source_map_id)
    labels = flatten_labels(labels_raw)
    markers = []
    seen: set[str] = set()
    skipped_unknown_labels = 0

    for point in points_raw:
        if not isinstance(point, dict):
            raise ValueError("Every point must be a JSON object.")
        required = {"id", "labelId", "x", "y"}
        missing = required - point.keys()
        if missing:
            raise ValueError(f"Point is missing fields: {', '.join(sorted(missing))}")
        source_id = str(point["id"])
        marker_id = f"hoyolab:{source_map_id}:{point.get('z', 'surface')}:{source_id}"
        if marker_id in seen:
            raise ValueError(f"Duplicate HoYoLAB point id: {marker_id}")
        seen.add(marker_id)
        label_id = str(point["labelId"])
        label = labels.get(label_id)
        if label is None:
            skipped_unknown_labels += 1
            continue
        x, y = float(point["x"]), float(point["y"])
        if not (x == x and y == y):
            raise ValueError(f"Non-finite coordinates for point {source_id}")
        marker = {
            "id": marker_id,
            "source": "hoyolab-public-map-snapshot",
            "source_map_id": source_map_id,
            "source_point_id": source_id,
            "map_id": map_id,
            "label_id": label_id,
            "name": label["name"],
            "category_path": label["path"],
            "icon": label["icon"],
            "coordinate_space": "hoyolab_map",
            "map_x": x,
            "map_y": y,
        }
        if point.get("z") is not None:
            marker["z"] = point["z"]
        markers.append(marker)

    markers.sort(key=lambda item: (item["label_id"], item["source_point_id"]))
    return {
        "schema_version": 1,
        "source": {
            "name": "HoYoLAB interactive map",
            "snapshot_format": "kxxoling/genshin-map-data",
            "map_id": source_map_id,
            "map_version": meta.get("mapVersion"),
            "game_version": meta.get("gameVersion"),
            "fetched_at": meta.get("fetchedAt"),
            "attribution": "Data originated from the public HoYoLAB interactive map; verify applicable terms before redistribution.",
        },
        "map": {
            "id": map_id,
            "origin": meta.get("origin"),
            "total_size": meta.get("totalSize"),
            "min_zoom": meta.get("minZoom"),
            "max_zoom": meta.get("maxZoom"),
        },
        "label_count": len(labels),
        "point_count": len(markers),
        "skipped_unknown_labels": skipped_unknown_labels,
        "markers": markers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path, help="Directory containing meta.json, labels.json and points.json")
    parser.add_argument("-o", "--output", type=Path, help="Output JSON path (default: stdout)")
    parser.add_argument("--map-key", help="Optional local catalogue key; source map ID remains preserved")
    args = parser.parse_args()
    result = import_snapshot(args.input_dir, map_key=args.map_key)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Imported {result['point_count']} points from HoYoLAB map {result['source']['map_id']} -> {args.output}")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
