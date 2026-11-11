"""Loads local reference tiles once and provides spatially-aware candidate ordering."""
from __future__ import annotations
import json
import logging
from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np

LOG = logging.getLogger(__name__)


@dataclass(slots=True)
class ReferenceTile:
    tile_id: str
    path: Path
    width: int
    height: int
    keypoints: list
    descriptors: np.ndarray
    neighbors: tuple[str, ...]


class ReferenceManager:
    def __init__(self, manifest_path: str | Path, *, max_features: int = 3500,
                 min_features: int = 14) -> None:
        self.manifest_path = Path(manifest_path).resolve()
        if not self.manifest_path.is_file():
            raise FileNotFoundError(
                f"Missing {self.manifest_path}. Copy manifest.example.json to manifest.json "
                "and add your own map crops under references/tiles/."
            )
        config = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self.monitor_index = int(config.get("monitor_index", 1))
        self.tiles: dict[str, ReferenceTile] = {}
        orb = cv2.ORB_create(nfeatures=max_features, scaleFactor=1.2,
                             nlevels=8, fastThreshold=12)
        entries = config.get("tiles", [])
        if not entries:
            raise ValueError("manifest.json must contain a non-empty 'tiles' array.")
        for item in entries:
            tile_id = str(item["id"])
            if tile_id in self.tiles:
                raise ValueError(f"Duplicate reference tile id: {tile_id}")
            image_path = (self.manifest_path.parent / item["image"]).resolve()
            image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
            if image is None:
                LOG.warning("Reference tile is missing or unreadable: %s", image_path)
                continue
            keypoints, descriptors = orb.detectAndCompute(image, None)
            if descriptors is None or len(keypoints) < min_features:
                LOG.warning("Reference tile %s has too few detectable features", tile_id)
                continue
            self.tiles[tile_id] = ReferenceTile(
                tile_id, image_path, image.shape[1], image.shape[0],
                keypoints, descriptors, tuple(str(v) for v in item.get("neighbors", []))
            )
            LOG.info("Indexed reference tile %s (%d ORB features)", tile_id, len(keypoints))
        if not self.tiles:
            raise RuntimeError("No valid reference tiles loaded; check image paths and image quality.")
        for tile in self.tiles.values():
            unknown = set(tile.neighbors) - self.tiles.keys()
            if unknown:
                LOG.warning("Tile %s references unknown neighbors: %s", tile.tile_id, sorted(unknown))

    def candidates(self, current_tile_id: str | None) -> list[ReferenceTile]:
        ordered: list[str] = []
        if current_tile_id in self.tiles:
            ordered.append(current_tile_id)
            ordered.extend(n for n in self.tiles[current_tile_id].neighbors
                           if n in self.tiles and n not in ordered)
        ordered.extend(tile_id for tile_id in self.tiles if tile_id not in ordered)
        return [self.tiles[tile_id] for tile_id in ordered]
