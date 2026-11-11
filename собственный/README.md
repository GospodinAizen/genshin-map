# Genshin Map Overlay

Desktop overlay prototype: local map reference tiles + ORB feature matching + homography marker projection.

## Run

Python 3.10+ recommended.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

Create `references/manifest.json` from `references/manifest.example.json`, add your own map crops to `references/tiles/`, then run:

```bash
python genshin.py
```

Press **M** to show/hide the click-through overlay.

## Tiles and markers

The manifest stores unique tile IDs and image paths relative to itself. Use high-resolution local crops with about 15–25% overlap between neighboring tiles. Marker x/y coordinates are pixel coordinates inside the corresponding tile. Add `"tile_id": "mondstadt_01"` to each marker record. If omitted, the current demo catalogue defaults to `mondstadt_01`.

Example:

```json
{"id":"chest_001","name":"Chest","type":"chest","tile_id":"mondstadt_01","x":512,"y":384}
```

Supported categories: chest, oculus, quest, puzzle, resource, challenge.

## Modules

- `screen_tracker.py`: cached ORB descriptors per tile, previous-tile-first matching, ratio filtering and RANSAC homography validation.
- `worker.py`: runs capture and CV on a worker thread.
- `marker_renderer.py`: pure projection/filtering logic.
- `marker_database.py`: validated catalogue and SQLite progress.
- `overlay.py`: transparent click-through Qt window.
- `hotkeys.py`: pynput-to-Qt signal bridge.

## Limitations

No map-reference images are included. The tracker cannot work until you add tiles and a manifest. The overlay is click-through, so clicking markers to mark them found is not implemented. Capture currently targets the first physical monitor; multi-monitor and DPI behavior need testing. Feature matching can fail under map rotation, heavy UI obstruction, effects, or repetitive terrain.
