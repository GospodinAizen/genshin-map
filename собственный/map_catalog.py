"""Multi-world/floor catalogue for full-map and minimap reference sets.

The catalogue is metadata only: image assets are imported locally from sources the
user is authorized to use. Each map owns an isolated reference manifest and marker set.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True, slots=True)
class MapDefinition:
    map_id: str
    name: str
    region: str
    floor: str
    modes: tuple[str, ...]
    reference_manifest: Path
    marker_file: Path
    enabled: bool = True
    source: str = "local"


class MapCatalog:
    """Loads and validates a versioned catalogue of every supported game map."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()
        if not self.path.is_file():
            raise FileNotFoundError(f"Map catalogue not found: {self.path}")
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if raw.get("schema_version") != 1:
            raise ValueError("map-catalog.json schema_version must be 1")
        self.default_map_id = raw.get("default_map_id")
        self.maps: dict[str, MapDefinition] = {}
        for item in raw.get("maps", []):
            map_id = str(item["id"]).strip()
            if not map_id or map_id in self.maps:
                raise ValueError(f"Empty or duplicate map id: {map_id!r}")
            modes = tuple(item.get("modes", ["full"]))
            if not modes or set(modes) - {"full", "minimap"}:
                raise ValueError(f"Invalid modes for map {map_id}: {modes}")
            reference = (self.path.parent / item["reference_manifest"]).resolve()
            markers = (self.path.parent / item.get("marker_file", "markers.json")).resolve()
            self.maps[map_id] = MapDefinition(
                map_id=map_id,
                name=str(item.get("name", map_id)),
                region=str(item.get("region", "unknown")),
                floor=str(item.get("floor", "surface")),
                modes=modes,
                reference_manifest=reference,
                marker_file=markers,
                enabled=bool(item.get("enabled", True)),
                source=str(item.get("source", "local")),
            )
        if not self.maps:
            raise ValueError("Map catalogue contains no maps.")
        if self.default_map_id not in self.maps:
            self.default_map_id = next(iter(self.maps))

    def list_maps(self, mode: str | None = None) -> list[MapDefinition]:
        if mode not in (None, "full", "minimap"):
            raise ValueError(f"Unknown map mode: {mode}")
        return [m for m in self.maps.values()
                if m.enabled and (mode is None or mode in m.modes)]

    def get(self, map_id: str) -> MapDefinition:
        try:
            return self.maps[map_id]
        except KeyError as exc:
            raise KeyError(f"Unknown map id: {map_id}") from exc

    def resolve_asset(self, map_id: str, relative_path: str) -> Path:
        """Resolve an asset while preventing paths escaping the catalogue directory."""
        root = self.path.parent
        candidate = (root / relative_path).resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError("Map asset path escapes the catalogue directory.")
        return candidate
