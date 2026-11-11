"""Reference-tile matching and screen-to-map homography estimation."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import mss
import numpy as np

LOG = logging.getLogger(__name__)


@dataclass(slots=True)
class ReferenceTile:
    tile_id: str
    image_size: tuple[int, int]
    keypoints: list
    descriptors: np.ndarray


class ScreenTracker:
    """Precomputes ORB descriptors once and matches the previous tile first."""

    def __init__(self, manifest_path: str | Path, *, max_features: int = 3500,
                 ratio_test: float = 0.74, min_matches: int = 14,
                 min_inliers: int = 11, min_inlier_ratio: float = 0.35) -> None:
        self.manifest_path = Path(manifest_path).resolve()
        if not self.manifest_path.is_file():
            raise FileNotFoundError(
                f"Reference manifest not found: {self.manifest_path}. "
                "Create it from references/manifest.example.json and add map tiles."
            )
        self.ratio_test = ratio_test
        self.min_matches = min_matches
        self.min_inliers = min_inliers
        self.min_inlier_ratio = min_inlier_ratio
        self.orb = cv2.ORB_create(nfeatures=max_features, scaleFactor=1.2,
                                  nlevels=8, fastThreshold=12)
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        self.sct = mss.mss()
        self.monitor = dict(self.sct.monitors[1])
        self.tiles = self._load_tiles()
        self._last_tile_id: str | None = None

    def _load_tiles(self) -> list[ReferenceTile]:
        data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if not data.get("tiles"):
            raise ValueError("Reference manifest contains no tiles.")
        tiles = []
        for item in data["tiles"]:
            path = (self.manifest_path.parent / item["image"]).resolve()
            image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if image is None:
                LOG.warning("Skipping missing/unreadable tile: %s", path)
                continue
            keypoints, descriptors = self.orb.detectAndCompute(image, None)
            if descriptors is None or len(keypoints) < self.min_matches:
                LOG.warning("Tile %s has too few ORB features", item["id"])
                continue
            tiles.append(ReferenceTile(str(item["id"]), (image.shape[1], image.shape[0]),
                                       keypoints, descriptors))
        if not tiles:
            raise RuntimeError("No usable reference tiles. Add map images under references/tiles/.")
        return tiles

    def capture_screen(self) -> np.ndarray:
        frame = np.asarray(self.sct.grab(self.monitor))
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)

    def detect(self) -> dict | None:
        frame = self.capture_screen()
        screen_points, screen_descriptors = self.orb.detectAndCompute(frame, None)
        if screen_descriptors is None or len(screen_points) < self.min_matches:
            return None
        candidates = sorted(self.tiles, key=lambda tile: tile.tile_id != self._last_tile_id)
        best = None
        for tile in candidates:
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
            ratio = inliers / len(good)
            if inliers < self.min_inliers or ratio < self.min_inlier_ratio:
                continue
            corners = np.float32([[0, 0], [tile.image_size[0], 0],
                                  [tile.image_size[0], tile.image_size[1]],
                                  [0, tile.image_size[1]]]).reshape(-1, 1, 2)
            projected = cv2.perspectiveTransform(corners, h).reshape(-1, 2)
            if not np.isfinite(projected).all():
                continue
            if np.ptp(projected[:, 0]) < frame.shape[1] * 0.12 or np.ptp(projected[:, 1]) < frame.shape[0] * 0.12:
                continue
            score = inliers * ratio
            if best is None or score > best["score"]:
                best = {"tile_id": tile.tile_id, "homography": h, "matches": len(good),
                        "inliers": inliers, "inlier_ratio": ratio,
                        "screen_size": (frame.shape[1], frame.shape[0]),
                        "monitor_origin": (self.monitor["left"], self.monitor["top"]),
                        "score": score}
        if best is None:
            return None
        self._last_tile_id = best["tile_id"]
        best.pop("score")
        return best

    def close(self) -> None:
        self.sct.close()
