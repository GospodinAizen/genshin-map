"""Multi-monitor map matcher with adaptive global acquisition and explicit diagnostics."""
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
    def __init__(self, manifest_path: str | Path, *, max_features: int = 2600,
                 ratio_test: float = 0.80, min_matches: int = 10,
                 min_inliers: int = 8, min_inlier_ratio: float = 0.25) -> None:
        self.manager = ReferenceManager(manifest_path, max_features=3500,
                                        min_features=min_matches)
        self.ratio_test, self.min_matches = ratio_test, min_matches
        self.min_inliers, self.min_inlier_ratio = min_inliers, min_inlier_ratio
        self.orb = cv2.ORB_create(nfeatures=max_features, scaleFactor=1.2,
                                  nlevels=10, fastThreshold=8)
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        self._global_tiles = list(self.manager.tiles.values())
        self._global_matcher = cv2.FlannBasedMatcher(
            dict(algorithm=6, table_number=12, key_size=20, multi_probe_level=2), {})
        for tile in self._global_tiles:
            self._global_matcher.add([tile.descriptors])
        self._global_matcher.train()
        self.sct = mss.mss()
        self._monitor_ids = (
            [self.manager.monitor_index] if self.manager.monitor_index != "auto"
            else list(range(1, len(self.sct.monitors)))
        )
        self._monitor_ids = [i for i in self._monitor_ids if 0 < i < len(self.sct.monitors)]
        if not self._monitor_ids:
            raise ValueError("Не найден физический монитор для захвата экрана.")
        self._last_tile_id = None
        self._last_detection = None
        self._misses = 0
        self.last_status = (
            f"Эталоны: {len(self._global_tiles)}; мониторы для проверки: "
            f"{', '.join(map(str, self._monitor_ids))}"
        )

    def _rank_global_candidates(self, descriptors: np.ndarray):
        try:
            pairs = self._global_matcher.knnMatch(descriptors, k=2)
            votes: Counter[int] = Counter()
            for pair in pairs:
                if len(pair) >= 2 and pair[0].distance < self.ratio_test * pair[1].distance:
                    votes[pair[0].imgIdx] += 1
            ranked = [self._global_tiles[i] for i, count in votes.most_common(24)
                      if count >= self.min_matches]
            return ranked or self._global_tiles
        except cv2.error:
            LOG.exception("Global reference search failed")
            return self._global_tiles

    def _match_frame(self, frame: np.ndarray, monitor: dict, monitor_id: int):
        points, descriptors = self.orb.detectAndCompute(frame, None)
        if descriptors is None or len(points) < self.min_matches:
            return None, f"Монитор {monitor_id}: мало деталей на экране ({len(points)})."
        candidates = (self._rank_global_candidates(descriptors)
                      if self._last_tile_id is None
                      else self.manager.candidates(self._last_tile_id))
        best = None
        for tile in candidates:
            pairs = self.matcher.knnMatch(tile.descriptors, descriptors, k=2)
            good = [a for pair in pairs if len(pair) == 2
                    for a, b in [pair] if a.distance < self.ratio_test * b.distance]
            if len(good) < self.min_matches:
                continue
            src = np.float32([tile.keypoints[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
            dst = np.float32([points[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
            h, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0,
                                         maxIters=3000, confidence=0.995)
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
            if width < frame.shape[1] * 0.06 or height < frame.shape[0] * 0.06:
                continue
            if width > frame.shape[1] * 12 or height > frame.shape[0] * 12:
                continue
            score = inliers * ratio
            if best is None or score > best["score"]:
                best = {
                    "tile_id": tile.tile_id, "homography": h,
                    "reference_origin": tile.reference_origin,
                    "reference_scale": tile.reference_scale,
                    "reference_zoom": int(round(np.log2(tile.reference_scale))),
                    "matches": len(good), "inliers": inliers,
                    "inlier_ratio": ratio, "confidence": ratio, "score": score,
                    "screen_size": (frame.shape[1], frame.shape[0]),
                    "monitor_origin": (monitor["left"], monitor["top"]),
                    "monitor_size": (monitor["width"], monitor["height"]),
                    "monitor_index": monitor_id,
                }
        return best, (
            f"Монитор {monitor_id}: совпадений не найдено; деталей {len(points)}, "
            f"эталонов проверено {len(candidates)}."
        )

    def detect(self) -> dict | None:
        best = None
        diagnostics = []
        for monitor_id in self._monitor_ids:
            monitor = dict(self.sct.monitors[monitor_id])
            try:
                raw = np.asarray(self.sct.grab(monitor))
                frame = cv2.cvtColor(raw, cv2.COLOR_BGRA2GRAY)
                candidate, reason = self._match_frame(frame, monitor, monitor_id)
                if candidate is not None and (best is None or candidate["score"] > best["score"]):
                    best = candidate
                else:
                    diagnostics.append(reason)
            except Exception as exc:
                LOG.exception("Screen capture failed for monitor %s", monitor_id)
                diagnostics.append(f"Монитор {monitor_id}: ошибка захвата — {exc}")
        if best is None:
            self.last_status = "Карта не распознана. " + " ".join(diagnostics)
            return self._on_miss()
        self._last_tile_id = best["tile_id"]
        self._misses = 0
        best.pop("score")
        self._last_detection = best
        self.last_status = (
            f"Карта распознана · монитор {best['monitor_index']} · {best['tile_id']} · "
            f"уверенность {best['confidence']:.0%} · совпадений {best['matches']} · "
            f"точных {best['inliers']}"
        )
        return best

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
