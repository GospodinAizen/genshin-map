"""Fast local-tile matcher with neighbor prioritization and temporal confidence."""
from __future__ import annotations
import logging
from collections import Counter
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
        self.ratio_test, self.min_matches = ratio_test, min_matches
        self.min_inliers, self.min_inlier_ratio = min_inliers, min_inlier_ratio
        self.orb = cv2.ORB_create(nfeatures=max_features, scaleFactor=1.2,
                                  nlevels=8, fastThreshold=12)
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        self._global_tiles = list(self.manager.tiles.values())
        self._global_matcher = cv2.FlannBasedMatcher(
            dict(algorithm=6, table_number=12, key_size=20, multi_probe_level=2), {})
        for tile in self._global_tiles:
            self._global_matcher.add([tile.descriptors])
        self._global_matcher.train()
        self.sct = mss.mss()
        monitor_index = self.manager.monitor_index
        if monitor_index <= 0 or monitor_index >= len(self.sct.monitors):
            raise ValueError(f"Invalid monitor_index={monitor_index}; available physical monitors: 1..{len(self.sct.monitors)-1}")
        self.monitor = dict(self.sct.monitors[monitor_index])
        self._last_tile_id = None
        self._last_detection = None
        self._misses = 0
        self.last_status = f"Трекер готов: {len(self._global_tiles)} эталонов; монитор {monitor_index}"

    def capture_screen(self) -> np.ndarray:
        frame = np.asarray(self.sct.grab(self.monitor))
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)

    def detect(self) -> dict | None:
        frame = self.capture_screen()
        screen_points, screen_descriptors = self.orb.detectAndCompute(frame, None)
        if screen_descriptors is None or len(screen_points) < self.min_matches:
            self.last_status = "На экране мало деталей для распознавания. Откройте полноэкранную карту Тейвата."
            return self._on_miss()
        best = None
        candidates = (self._rank_global_candidates(screen_descriptors)
                      if self._last_tile_id is None else self.manager.candidates(self._last_tile_id))
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
            if width > frame.shape[1] * 64 or height > frame.shape[0] * 64:
                continue
            score = inliers * ratio
            if best is None or score > best["score"]:
                best = {"tile_id": tile.tile_id, "homography": h,
                        "reference_origin": tile.reference_origin,
                        "reference_scale": tile.reference_scale,
                        "reference_zoom": int(round(np.log2(tile.reference_scale))),
                        "matches": len(good), "inliers": inliers,
                        "inlier_ratio": ratio, "confidence": ratio, "score": score}
        if best is None:
            self.last_status = (
                f"Карта не совпала с эталонами ({len(candidates)} проверено). "
                "Проверьте: открыта ли карта Тейвата, не включён ли другой экран/монитор, "
                "не изменён ли масштаб интерфейса."
            )
            return self._on_miss()
        self._last_tile_id = best["tile_id"]
        self._misses = 0
        best.pop("score")
        best.update({"screen_size": (frame.shape[1], frame.shape[0]),
                     "monitor_origin": (self.monitor["left"], self.monitor["top"]),
                     "monitor_size": (self.monitor["width"], self.monitor["height"])})
        self._last_detection = best
        self.last_status = (
            f"Карта распознана: {best['tile_id']} · {best['confidence']:.0%} "
            f"· совпадений {best['matches']} · точных {best['inliers']}"
        )
        return best

    def _rank_global_candidates(self, screen_descriptors: np.ndarray):
        try:
            pairs = self._global_matcher.knnMatch(screen_descriptors, k=2)
            votes: Counter[int] = Counter()
            for pair in pairs:
                if len(pair) < 2:
                    continue
                first, second = pair[0], pair[1]
                if first.distance < self.ratio_test * second.distance:
                    votes[first.imgIdx] += 1
            ranked = [self._global_tiles[index] for index, count in votes.most_common(16)
                      if count >= self.min_matches]
            if ranked:
                return ranked
        except cv2.error:
            LOG.exception("Global map search failed; falling back to a full reference scan")
        return list(self._global_tiles)

    def _on_miss(self) -> dict | None:
        self._misses += 1
        if self._misses >= 3:
            self._last_tile_id = None
        if self._misses <= 1 and self._last_detection is not None:
            return self._last_detection
        self._last_detection = None
        return None

    def close(self) -> None:
        self.sct.close()
