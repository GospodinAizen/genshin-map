"""Minimap-localized tracker using an independently configured screen ROI.

The reference manifest is map-specific. Coordinates are projected into the same
monitor coordinate space as the full-map tracker, so the overlay can render either.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from screen_tracker import ScreenTracker


class MinimapTracker(ScreenTracker):
    def __init__(self, manifest_path: str | Path, *, max_features: int = 3500,
                 ratio_test: float = 0.74, min_matches: int = 10,
                 min_inliers: int = 8, min_inlier_ratio: float = 0.30) -> None:
        super().__init__(manifest_path, max_features=max_features,
                         ratio_test=ratio_test, min_matches=min_matches,
                         min_inliers=min_inliers, min_inlier_ratio=min_inlier_ratio)
        import json
        config = json.loads(self.manager.manifest_path.read_text(encoding="utf-8"))
        roi = config.get("minimap_roi")
        if not isinstance(roi, dict):
            self.close()
            raise ValueError("Minimap manifest requires minimap_roi: {x,y,width,height}.")
        # ROI values are fractions of the selected monitor, not desktop coordinates.
        values = [float(roi[k]) for k in ("x", "y", "width", "height")]
        if any(v < 0 or v > 1 for v in values) or values[2] <= 0 or values[3] <= 0:
            self.close()
            raise ValueError("minimap_roi values must be normalized fractions in [0,1].")
        self.roi = tuple(values)
        self.mask_circle = bool(roi.get("circle_mask", True))

    def capture_screen(self) -> np.ndarray:
        x, y, width, height = self.roi
        left = self.monitor["left"] + round(x * self.monitor["width"])
        top = self.monitor["top"] + round(y * self.monitor["height"])
        roi_width = max(32, round(width * self.monitor["width"]))
        roi_height = max(32, round(height * self.monitor["height"]))
        frame = np.asarray(self.sct.grab({
            "left": left, "top": top, "width": roi_width, "height": roi_height
        }))
        gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
        if self.mask_circle:
            mask = np.zeros(gray.shape, dtype=np.uint8)
            cv2.circle(mask, (gray.shape[1] // 2, gray.shape[0] // 2),
                       min(gray.shape) // 2 - 2, 255, -1)
            gray = cv2.bitwise_and(gray, gray, mask=mask)
        self._roi_origin = (left - self.monitor["left"], top - self.monitor["top"])
        return gray

    def detect(self) -> dict | None:
        result = super().detect()
        if result is None:
            return None
        # Homography currently maps tile -> ROI. Translate it to monitor-local space.
        ox, oy = getattr(self, "_roi_origin", (0, 0))
        translation = np.asarray([[1.0, 0.0, ox], [0.0, 1.0, oy],
                                  [0.0, 0.0, 1.0]], dtype=np.float64)
        result = dict(result)
        result["homography"] = translation @ result["homography"]
        result["capture_mode"] = "minimap"
        return result
