"""Pure marker projection helpers."""
from __future__ import annotations
import cv2
import numpy as np
import zlib

COLORS = {"chest": (0, 190, 255), "oculus": (80, 255, 100),
          "quest": (255, 180, 50), "puzzle": (220, 80, 255),
          "resource": (80, 220, 255), "challenge": (255, 80, 80)}


def prepare_markers(markers: list[dict], detection: dict | None,
                    found_ids: set[str], enabled_types: set[str]) -> list[dict]:
    if detection is None:
        return []
    active_map = detection.get("map_id")
    candidates = [
        marker for marker in markers
        if marker["tile_id"] == detection["tile_id"]
        and marker["id"] not in found_ids
        and marker["type"] in enabled_types
        and (active_map is None or marker.get("map_id", "teyvat_surface") == active_map)
    ]
    if not candidates:
        return []

    # Transform all source points in one OpenCV call, then cull off-screen markers.
    # The official Teyvat snapshot contains tens of thousands of points; one
    # perspectiveTransform per marker would stall the overlay every refresh.
    source = np.asarray(
        [[[marker["x"], marker["y"]]] for marker in candidates],
        dtype=np.float32,
    )
    projected = cv2.perspectiveTransform(source, detection["homography"]).reshape(-1, 2)
    width, height = detection.get("screen_size", (0, 0))
    result = []
    for marker, (x, y) in zip(candidates, projected):
        if not np.isfinite((x, y)).all():
            continue
        if width and height and not (-32 <= x <= width + 32 and -32 <= y <= height + 32):
            continue
        result.append({**marker, "screen_x": float(x), "screen_y": float(y)})
    return result


def marker_color(marker_type: str) -> tuple[int, int, int]:
    known = COLORS.get(marker_type)
    if known is not None:
        return known
    # Stable per-category color across launches (unlike Python's randomized hash()).
    palette = ((70, 190, 255), (255, 150, 70), (120, 230, 150),
               (210, 130, 255), (255, 220, 90), (90, 220, 220),
               (255, 110, 150), (170, 210, 255))
    return palette[zlib.crc32(marker_type.encode("utf-8")) % len(palette)]
