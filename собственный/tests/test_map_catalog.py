import json
import pytest
from map_catalog import MapCatalog


def test_catalog_lists_modes_and_resolves_paths(tmp_path):
    (tmp_path / "refs").mkdir()
    manifest = tmp_path / "catalog.json"
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "default_map_id": "surface",
        "maps": [
            {"id": "surface", "name": "Surface", "region": "teyvat",
             "floor": "surface", "modes": ["full", "minimap"],
             "reference_manifest": "refs/surface.json"},
            {"id": "underground", "region": "chasm", "floor": "deep",
             "modes": ["full"], "reference_manifest": "refs/deep.json"}
        ]
    }), encoding="utf-8")
    catalog = MapCatalog(manifest)
    assert [m.map_id for m in catalog.list_maps("minimap")] == ["surface"]
    assert catalog.get("underground").floor == "deep"
    assert catalog.resolve_asset("surface", "refs/surface.json") == (tmp_path / "refs/surface.json").resolve()


def test_catalog_rejects_asset_path_escape(tmp_path):
    manifest = tmp_path / "catalog.json"
    manifest.write_text(json.dumps({"schema_version": 1, "maps": [
        {"id": "surface", "modes": ["full"], "reference_manifest": "refs.json"}
    ]}), encoding="utf-8")
    with pytest.raises(ValueError):
        MapCatalog(manifest).resolve_asset("surface", "../outside.png")


def test_catalog_rejects_duplicate_ids(tmp_path):
    manifest = tmp_path / "catalog.json"
    item = {"id": "same", "modes": ["full"], "reference_manifest": "refs.json"}
    manifest.write_text(json.dumps({"schema_version": 1, "maps": [item, item]}), encoding="utf-8")
    with pytest.raises(ValueError):
        MapCatalog(manifest)
