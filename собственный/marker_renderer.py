import cv2
import numpy as np


COLORS = {
    "chest": (0, 190, 255),
    "oculus": (80, 255, 100),
    "quest": (255, 180, 50),
    "puzzle": (220, 80, 255),
    "resource": (80, 220, 255),
    "challenge": (255, 80, 80)
}


def transform_marker(x, y, homography):
    point = np.array(
        [[[float(x), float(y)]]],
        dtype=np.float32
    )

    transformed = cv2.perspectiveTransform(
        point,
        homography
    )

    return (
        int(transformed[0][0][0]),
        int(transformed[0][0][1])
    )


def prepare_markers(markers, detection, database):
    if detection is None:
        return []

    homography = detection["homography"]
    result = []

    for marker in markers:
        if database.is_found(marker["id"]):
            continue

        x, y = transform_marker(
            marker["x"],
            marker["y"],
            homography
        )

        result.append({
            "id": marker["id"],
            "x": x,
            "y": y,
            "name": marker["name"],
            "type": marker["type"]
        })

    return result


def marker_color(marker_type):
    return COLORS.get(
        marker_type,
        (255, 255, 255)
    )