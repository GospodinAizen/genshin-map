# Genshin Map Overlay

Desktop prototype: recognize the visible game map against local reference tiles and project custom markers into a transparent overlay.

## Install and run

Python 3.10+ recommended. Run the following commands from the repository root:

```bash
cd собственный
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

1. Copy `references/manifest.example.json` to `references/manifest.json`.
2. Put your own map crops under `references/tiles/`.
3. Edit tile IDs, paths and neighbor lists in the manifest.
4. Edit `marker.json`; x/y are pixel coordinates inside the tile named by tile_id.
5. Run `python genshin.py`.

Hotkeys: **M** toggles the overlay; **F6** toggles the control panel; **F7** toggles marker interaction. In F7 mode, left-click a marker to mark it found and right-click to restore it; only marker hit areas intercept input, while the rest of the game remains clickable.

## Tiles

The reference manager precomputes ORB descriptors once. It tries the last recognized tile, then declared neighbors, then all remaining tiles as fallback. Neighbor crops should overlap by about 15–25%. Use clear crops at consistent scale and orientation, avoiding UI elements and labels when possible.

Set `monitor_index` in the manifest if needed. MSS index 1 is the first physical display. No game-map imagery is included; supply images you are permitted to use.

## Controls

The control panel shows markers for the current tile. Check/uncheck a marker to mark it found/unfound; state persists in `data/progress.db`. Category checkboxes independently hide/show types. In normal mode the overlay is click-through. Press F7 to make only marker hitboxes interactive: left-click marks found, right-click restores the marker; all other screen areas continue passing input to the game.

## Modules

- `reference_manager.py`: tile loading, descriptor cache, neighbor ordering.
- `screen_tracker.py`: capture, ORB matching, RANSAC homography and confidence checks.
- `worker.py`: background CV worker.
- `marker_renderer.py`: coordinate projection and filters.
- `marker_database.py`: validated catalogue and SQLite progress.
- `overlay.py`: transparent click-through overlay with optional marker-only hit testing.
- `control_panel.py`: filters and progress controls.
- `hotkeys.py`: M/F6/F7 hotkeys bridged safely into Qt.

## Limitations

This prototype has not been tested against a live Genshin client here. Reference images and a ready-to-use manifest must be supplied locally. The tracker assumes fixed map scale/orientation within a tile; zoom, rotation, UI obstruction and repetitive terrain can reduce accuracy. Multi-monitor and mixed-DPI behavior needs real-device testing. Marker positions are currently edited in JSON; a visual marker editor is not included.
