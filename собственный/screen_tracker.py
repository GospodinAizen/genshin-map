"""Fast local-tile matcher with neighbor prioritization and temporal confidence."""
from __future__ import annotations

import logging
from pathlib import Path

import cv2
import mss
import numpy as np

from reference_manager import ReferenceManager

LOG = logging.getLogger(__name__)


class ScreenTracker:
    def __init__(self, manifest_path: str | Path, *, max_features: int = 900,
                 ratio_test: float = 0.74, min_matches: int = 14,
                 min_inliers: int = 11, min_inlier_ratio: float = 0.35) -> None:
        self.manager = ReferenceManager(manifest_path, max_features=max_features,
                                        min_features=min_matches)
        self.ratio_test = ratio_test
        self.min_matches = min_matches
        self.min_inliers = min_inliers
        self.min_inlier_ratio = min_inlier_ratio
        self.orb = cv2.ORB_create(nfeatures=max_features, scaleFactor=1.2,
                                  nlevels=8, fastThreshold=12)
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        self.sct = mss.mss()
        monitor_index = self.manager.monitor_index
        if monitor_index <= 0 or monitor_index >= len(self.sct.monitors):
            raise ValueError(f"Invalid monitor_index={monitor_index}; available physical monitors: 1..{len(self.sct.monitors)-1}")
        self.monitor = dict(self.sct.monitors[monitor_index])
        self._last_tile_id: str | None = None
        self._last_detection: dict | None = None
        self._misses = 0

    def capture_screen(self) -> np.ndarray:
        frame = np.asarray(self.sct.grab(self.monitor))
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)

    def detect(self) -> dict | None:
        frame = self.capture_screen()
        screen_points, screen_descriptors = self.orb.detectAndCompute(frame, None)
        if screen_descriptors is None or len(screen_points) < self.min_matches:
            return self._on_miss()

        best = None
        for tile in self.manager.candidates(self._last_tile_id):
            pairs = self.matcher.knnMatch(tile.descriptors, screen_descriptors, k=2)
            good = [a for pair in pairs if len(pair) == 2
                    for a, b in [pair] if a.distance < self.ratio_test * b.distance]
            if len(good) < self.min_matches:
                continue
            src = np.float32([tile.keypoints[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
            dst = np.float32([screen_points[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
            h, mask = cv2.findHomography(src, dst, cv2.RANSAC, 4.0,
                                         maxIters=2500, confidence=0.995)
            if h is None or mask is None or not np.isfinite(h).all():
                continue
            inliers = int(mask.ravel().sum())
            ratio = inliers / max(len(good), 1)
            if inliers < self.min_inliers or ratio < self.min_inlier_ratio:
                continue
            corners = np.float32([[0, 0], [tile.width, 0], [tile.width, tile.height],
                                  [0, tile.height]]).reshape(-1, 1, 2)
            projected = cv2.perspectiveTransform(corners, h).reshape(-1, 2)
            if not np.isfinite(projected).all():
                continue
            width, height = np.ptp(projected[:, 0]), np.ptp(projected[:, 1])
            if width < frame.shape[1] * 0.12 or height < frame.shape[0] * 0.12:
                continue
            # A projected tile should not be an extreme sliver or astronomically large.
            if width > frame.shape[1] * 64 or height > frame.shape[0] * 64:
                continue
            score = inliers * ratio
            if best is None or score > best["score"]:
                best = {
                    "tile_id": tile.tile_id,
                    "homography": h,
                    "reference_origin": tile.reference_origin,
                    "reference_scale": tile.reference_scale,
                    "reference_zoom": int(round(np.log2(tile.reference_scale))),
                    "matches": len(good),
                        "inliers": inliers, "inlier_ratio": ratio, "confidence": ratio, "score": score}

        if best is None:
            return self._on_miss()
        self._last_tile_id = best["tile_id"]
        self._misses = 0
        best.pop("score")
        best.update({
            "screen_size": (frame.shape[1], frame.shape[0]),
            "monitor_origin": (self.monitor["left"], self.monitor["top"]),
            "monitor_size": (self.monitor["width"], self.monitor["height"]),
        })
        self._last_detection = best
        return best

    def _on_miss(self) -> dict | None:
        self._misses += 1
        if self._misses >= 3:
            self._last_tile_id = None
        # Do not display stale positions indefinitely; tolerate one missed frame.
        if self._misses <= 1 and self._last_detection is not None:
            return self._last_detection
        self._last_detection = None
        return None

    def close(self) -> None:
        self.sct.close()
