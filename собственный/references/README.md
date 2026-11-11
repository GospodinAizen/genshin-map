# Reference tiles

Put your local reference image crops in `tiles/`. Copy `manifest.example.json` to `manifest.json` and update the tile list. Do not redistribute copyrighted map imagery unless you have permission.

Use unique tile IDs. Marker records refer to those IDs using `tile_id`. Neighboring tiles should overlap by roughly 15–25% to make transitions less brittle. The example manifest is only a template; its image files are not included.
