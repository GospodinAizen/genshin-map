import cv2
import numpy as np


COLORS = {
    "chest": (0, 190, 255),
    "oculus": (80, 255, 100),
    "quest": (255, 180, 50),
    "puzzle": (220, 80, 255),
    "resource": (80, 220, 255),
    "challenge": (255, 80, 80),
}


def transform_marker(x, y, homography):
    point = np.array([[[float(x), float(y)]]], dtype=np.float32)
    transformed = cv2.perspectiveTransform(point, homography)
    px, py = transformed[0][0]
    if not np.isfinite(px) or not np.isfinite(py):
        raise ValueError("Преобразование метки вернуло некорректные координаты")
    return int(round(px)), int(round(py))


def prepare_markers(markers, detection, database, enabled_categories=None):
    if detection is None:
        return []
    homography = detection.get("homography")
    if homography is None:
        return []
    found = database.get_found_ids()
    enabled = set(COLORS) if enabled_categories is None else enabled_categories
    width, height = detection.get("screen_size", (0, 0))
    result = []
    for marker in markers:
        if marker["id"] in found or marker["type"] not in enabled:
            continue
        x, y = transform_marker(marker["x"], marker["y"], homography)
        if width and height and not (0 <= x < width and 0 <= y < height):
            continue
        result.append({
            "id": marker["id"], "x": x, "y": y,
            "name": marker["name"], "type": marker["type"],
        })
    return result


def marker_color(marker_type):
    return COLORS.get(marker_type, (255, 255, 255))
