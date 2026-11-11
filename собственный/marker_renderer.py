"""Pure marker projection helpers."""
from __future__ import annotations
import cv2
import numpy as np

COLORS = {"chest": (0, 190, 255), "oculus": (80, 255, 100),
          "quest": (255, 180, 50), "puzzle": (220, 80, 255),
          "resource": (80, 220, 255), "challenge": (255, 80, 80)}


def prepare_markers(markers: list[dict], detection: dict | None,
                    found_ids: set[str], enabled_types: set[str]) -> list[dict]:
    if detection is None:
        return []
    result = []
    for marker in markers:
        if marker["tile_id"] != detection["tile_id"] or marker["id"] in found_ids:
            continue
        if marker["type"] not in enabled_types:
            continue
        point = np.asarray([[[marker["x"], marker["y"]]]], dtype=np.float32)
        x, y = cv2.perspectiveTransform(point, detection["homography"])[0, 0]
        result.append({**marker, "screen_x": float(x), "screen_y": float(y)})
    return result


def marker_color(marker_type: str) -> tuple[int, int, int]:
    return COLORS.get(marker_type, (255, 255, 255))
