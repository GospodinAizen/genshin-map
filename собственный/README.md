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
4. Run `python genshin.py`.

Hotkeys: **M** toggles overlay; **F6** toggles controls; **F7** toggles marker interaction.

## HoYoLAB snapshot importer

The importer consumes a local snapshot with `meta.json`, `labels.json`, and `points.json` (the compact JSON layout produced by `kxxoling/genshin-map-data`). It retains original point/label IDs, nested category paths, icon paths, map coordinates, z-level, map version, and source attribution.

```bash
python hoyolab_importer.py ./path/to/snapshot -o ./data/hoyolab-map-2.json
```

The importer does not fabricate missing labels or names. Points referring to unknown labels are counted and skipped. IDs are namespaced by source map and z-level to avoid collisions.

**Important coordinate boundary:** imported coordinates are in the HoYoLAB map coordinate space (`coordinate_space=hoyolab_map`), not pixels inside a local reference tile. They are intentionally not fed into the existing tile-pixel renderer until a verified transform from the source map's coordinate system to the selected reference-tile set is configured. The importer is a safe data-ingestion stage, not a claim that all imported markers are already rendered in-game.

The referenced public snapshot project currently documents a Teyvat snapshot (`map_id=2`). This does not establish complete coverage of every region, underground floor, domain, or future HoYoLAB layer. Each additional map needs its own verified source snapshot and catalogue entry. No login bypass or anti-bot evasion is implemented.

## HoYoLAB snapshot updater

The updater checks the latest public release from kxxoling/genshin-map-data, selects the matching full Teyvat archive, verifies its declared SHA-256 digest (when supplied), and installs it into the OS user cache. It does not put the ~80 MB map archive into this git repository.

```bash
# Check the upstream release without downloading
python hoyolab_updater.py --check

# Download, validate, import and atomically install the full Teyvat snapshot
python hoyolab_updater.py

# Reinstall the same release if the local cache needs repair
python hoyolab_updater.py --force
```

Default cache locations are %LOCALAPPDATA%/genshin-map-overlay/hoyolab/teyvat on Windows and ~/.cache/genshin-map-overlay/hoyolab/teyvat on Linux/macOS (or XDG_CACHE_HOME when set). Use --cache-dir to override. The installed folder contains upstream meta.json, labels.json, points.json, icons and tiles, plus markers.normalized.json and upstream-release.json.

Extraction rejects traversal paths, links and special files, enforces archive/member/expanded-size limits, checks archive size and release digest, validates the snapshot JSON through the importer, and swaps the new snapshot into place only after validation. Tests use local fixtures and do not access the network.

This updater currently downloads the full Teyvat snapshot only. It does not claim that every underground map, domain, event map, or future HoYoLAB layer is present. Normalized coordinates remain in HoYoLAB map space; this update does not yet wire the tiles or coordinates into the live overlay renderer.

## Multi-map architecture

`map-catalog.example.json` defines independent map identities. Every map has a stable ID, region, floor, supported capture modes, its own reference manifest, and its own marker file. Keep the catalogue data-driven; do not assume a fixed region list.

## Full map and minimap

- `screen_tracker.py`: full-frame ORB matching, RANSAC homography and confidence checks.
- `minimap_tracker.py`: independent normalized screen ROI, optional circular feature mask, and coordinate translation into monitor space. Configure `minimap_roi` in a minimap reference manifest using fractions of the monitor (0..1).
- `map_catalog.py`: versioned map/floor catalogue and safe local asset path resolution.
- `reference_manager.py`: cached ORB descriptors and neighbor-prioritized tile lookup.
- `marker_renderer.py`: map-aware marker projection and category filtering.
- `marker_database.py`: marker validation and persistent SQLite progress.

A minimap reference set is not interchangeable with a full-map tile set. It must contain visual reference crops prepared for the minimap scale and orientation. Live-game validation remains necessary.

## Current status and limitations

The map catalogue, minimap-localization foundation, and lossless HoYoLAB snapshot importer are implemented. The existing `genshin.py` runtime is still a legacy single-manifest runtime: automatic map discovery/switching, projection of HoYoLAB map coordinates into tile coordinates, and live client validation are not yet complete. Reference assets and exact minimap ROI depend on screen resolution and UI scale. Zoom, UI obstruction, repeated terrain, mixed DPI, and multiple monitors require real-device testing.
