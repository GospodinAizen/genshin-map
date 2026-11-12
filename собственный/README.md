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

For the HoYoLAB-backed first in-game prototype on Windows, use `Запустить_тест.bat` (instructions below). The legacy manual-reference mode remains available with `python genshin.py` after preparing `references/manifest.json` and its image files.

Hotkeys: **M** toggles overlay; **F6** toggles controls; **F7** toggles marker interaction.

## HoYoLAB snapshot importer

The importer consumes a local snapshot with `meta.json`, `labels.json`, and `points.json` (the compact JSON layout produced by `kxxoling/genshin-map-data`). It retains original point/label IDs, nested category paths, icon paths, map coordinates, z-level, map version, and source attribution.

```bash
python hoyolab_importer.py ./path/to/snapshot -o ./data/hoyolab-map-2.json
```

The importer does not fabricate missing labels or names. Points referring to unknown labels are counted and skipped. IDs are namespaced by source map and z-level to avoid collisions.

**Coordinate transform:** HoYoLAB's public map metadata defines `world_pixel = point + origin`; each zoom level has scale `2 ** zoom` and 256×256 px source tiles. `hoyolab_runtime.py` builds 4×4 tile reference mosaics at every published zoom level (currently -4 through 0), records each mosaic's map-space origin, and projects source coordinates through the matched mosaic. The tracker uses approximate global descriptor search for initial acquisition, then prioritizes the current mosaic and its neighbors; after tracking loss it reacquires globally. This replaces the single low-resolution world image that could not reliably match zoomed-in game maps. Every point's original `z_level` is retained and exposed as a selectable layer in the Russian control panel. The public Teyvat snapshot does not provide a separate visual tile pyramid for every underground interior, so this selector filters the official points by z-level; it does not yet claim automatic recognition of underground interiors.

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

Default cache locations are %LOCALAPPDATA%/genshin-map-overlay/hoyolab/teyvat on Windows and ~/.cache/genshin-map-overlay/hoyolab/teyvat on Linux/macOS (or XDG_CACHE_HOME when set). Use --cache-dir to override. The installed folder contains upstream meta.json, labels.json, points.json, icons and tiles, plus markers.normalized.json, markers.runtime.json, references/manifest.json, multiscale reference mosaics, and upstream-release.json. The updater also requests the official Russian label locale and preserves the downloaded local icon files; if HoYoLAB does not provide Russian labels, it falls back to the source labels and the local translation table.

Extraction rejects traversal paths, links and special files, enforces archive/member/expanded-size limits, checks archive size and release digest, validates the snapshot JSON through the importer, and swaps the new snapshot into place only after validation. Tests use local fixtures and do not access the network.

This updater currently downloads the full Teyvat snapshot only. It does not claim that every underground map, domain, event map, or future HoYoLAB layer is present. The updater builds a multiscale reference catalogue and runtime marker file used by the overlay. All point z-levels are retained and can be selected manually in the panel. Separate underground map imagery and automatic floor recognition, minimap projection, and other HoYoLAB map IDs are still unfinished.

## Multi-map architecture

`map-catalog.example.json` defines independent map identities. Every map has a stable ID, region, floor, supported capture modes, its own reference manifest, and its own marker file. Keep the catalogue data-driven; do not assume a fixed region list.

## Full map and minimap

- `screen_tracker.py`: multiscale ORB matching, approximate global descriptor search, RANSAC homography and confidence checks.
- `minimap_tracker.py`: independent normalized screen ROI, optional circular feature mask, and coordinate translation into monitor space. Configure `minimap_roi` in a minimap reference manifest using fractions of the monitor (0..1).
- `map_catalog.py`: versioned map/floor catalogue and safe local asset path resolution.
- `reference_manager.py`: cached ORB descriptors and neighbor-prioritized tile lookup.
- `marker_renderer.py`: map-aware marker projection and category filtering.
- `marker_database.py`: marker validation and persistent SQLite progress.

A minimap reference set is not interchangeable with a full-map tile set. It must contain visual reference crops prepared for the minimap scale and orientation. Live-game validation remains necessary.

## Current status and limitations

The HoYoLAB surface runtime is wired into `genshin.py`: it downloads the public Teyvat snapshot, builds references from all published zoom levels, attempts Russian labels, projects surface markers, and renders the official marker icons over a matched full map. It remains experimental: matching has not been validated on every UI scale, aspect ratio, monitor layout, or on the user's PC. Manual z-level filtering is available; separate underground floor imagery and automatic floor recognition, minimap projection, automatic map switching, and live validation remain unfinished.

## First user test (Windows)

1. Install Python 3.11 or newer and enable the Python Launcher.
2. Download this branch as a ZIP from GitHub and extract it.
3. Open the `собственный` folder and double-click `Запустить_тест.bat`.
4. The launcher creates a virtual environment, installs dependencies, downloads and validates the latest public Teyvat snapshot, builds multiscale reference mosaics, and starts the overlay.
5. Start Genshin Impact in borderless/windowed mode, open the in-game full map, and press **M** to show/hide the overlay. Press **F6** for the category/progress panel (including the available z-level selector) and **F7** to enable marker clicks (left-click = found, right-click = unmark).

This test build uses the official HoYoLAB Teyvat surface points and map tiles. It does not require user screenshots or manually prepared map crops. The game map must be visible on the selected monitor (monitor 1 by default). If recognition does not lock on, the overlay will show no markers rather than inventing positions. The minimap and underground floors are not yet part of this test.
