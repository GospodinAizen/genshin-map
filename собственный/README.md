# Genshin Map Overlay

Desktop overlay foundation for multi-region Genshin maps. It separates map identity/floors from reference tiles and supports independent full-map and minimap localization pipelines.

## Install and run

Python 3.10+ recommended. From the repository root:

```bash
cd собственный
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

The current runnable prototype still uses the legacy single-map entry point:
1. Copy `references/manifest.example.json` to `references/manifest.json`.
2. Put permitted local reference crops under `references/tiles/`.
3. Edit tile IDs, paths and neighbor lists.
4. Edit `marker.json`; x/y are pixel coordinates inside a tile.
5. Run `python genshin.py`.

Hotkeys: **M** toggles overlay; **F6** toggles controls; **F7** toggles marker interaction.

## Multi-map architecture

`map-catalog.example.json` defines independent map identities. Every map has a stable ID, region, floor, supported capture modes, its own reference manifest, and its own marker file. Use it as the template for all HoYoLAB map layers, including surface regions, underground floors, Enkanomiya, the Chasm, domains, and future additions. Do not assume a fixed region list: the catalogue is data-driven.

Markers may include `map_id`; progress is stored by globally unique marker ID and remains shared between views. The renderer filters markers by the detected map identity.

## Full map and minimap

- `screen_tracker.py`: full-frame ORB matching, RANSAC homography and confidence checks.
- `minimap_tracker.py`: independent normalized screen ROI, optional circular feature mask, and coordinate translation into monitor space. Configure `minimap_roi` in a minimap reference manifest using fractions of the monitor (0..1).
- `map_catalog.py`: versioned multi-map/floor catalogue and safe local asset path resolution.
- `reference_manager.py`: cached ORB descriptors and neighbor-prioritized tile lookup.
- `marker_renderer.py`: map-aware marker projection and category filtering.
- `marker_database.py`: marker validation and persistent SQLite progress.

A minimap reference set is not interchangeable with a full-map tile set. It must contain visual reference crops prepared for the minimap scale and orientation. The tracker can estimate rotation through homography, but live-game validation is still required.

## Reference data and rights

No HoYoverse map imagery or marker database is bundled. The application accepts local images and metadata that the user is authorized to use. The catalogue/import boundary is deliberately independent of any private or undocumented HoYoLAB endpoint; no authentication bypass, anti-bot evasion, or automatic redistribution is implemented. A future importer should use an official/exported source with permission and preserve source attribution and licensing metadata.

## Current status and limitations

The multi-map catalogue and minimap-localization foundation are implemented, but the existing `genshin.py` runtime is not yet wired to run multiple map trackers concurrently or switch all maps automatically. Full/minimap recognition, map selection, and per-map marker-file loading need integration and live client validation. Reference assets and exact minimap ROI depend on the user's resolution/UI scale. Zoom, UI obstruction, repeated terrain, mixed DPI, and multiple monitors require real-device testing. Marker editing is currently JSON-based.
