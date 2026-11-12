import io
import json
import tarfile

import pytest

import hoyolab_updater as updater


def make_archive(path, entries):
    with tarfile.open(path, "w:gz") as archive:
        for name, payload, kind in entries:
            info = tarfile.TarInfo(name)
            if kind == "dir":
                info.type = tarfile.DIRTYPE
                archive.addfile(info)
            else:
                data = payload.encode("utf-8")
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))


def test_safe_extract_finds_snapshot_root(tmp_path):
    archive = tmp_path / "snapshot.tar.gz"
    make_archive(archive, [
        ("data/teyvat/", "", "dir"),
        ("data/teyvat/meta.json", '{"mapId":2}', "file"),
        ("data/teyvat/labels.json", "[]", "file"),
        ("data/teyvat/points.json", "[]", "file"),
    ])
    root = updater.safe_extract(archive, tmp_path / "out")
    assert root == tmp_path / "out/data/teyvat"
    assert (root / "meta.json").is_file()


def test_safe_extract_rejects_path_traversal(tmp_path):
    archive = tmp_path / "bad.tar.gz"
    make_archive(archive, [("../escape.txt", "nope", "file")])
    with pytest.raises(RuntimeError, match="Unsafe archive path"):
        updater.safe_extract(archive, tmp_path / "out")
    assert not (tmp_path / "escape.txt").exists()


def test_safe_extract_rejects_symlinks(tmp_path):
    archive = tmp_path / "link.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        info = tarfile.TarInfo("snapshot/link")
        info.type = tarfile.SYMTYPE
        info.linkname = "../../outside"
        tar.addfile(info)
    with pytest.raises(RuntimeError, match="Unsupported archive entry"):
        updater.safe_extract(archive, tmp_path / "out")


def test_latest_asset_requires_exact_full_snapshot(monkeypatch):
    payload = {
        "tag_name": "v7.2.0",
        "assets": [
            {"name": "teyvat-diff-v7.1.3-v7.2.0.tar.gz", "size": 10, "browser_download_url": "https://example/diff"},
            {"name": "teyvat-full-v7.2.0.tar.gz", "size": 20,
             "browser_download_url": "https://example/full", "digest": "sha256:abc"},
        ],
    }

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return json.dumps(payload).encode()

    monkeypatch.setattr(updater, "_request", lambda *args, **kwargs: Response())
    asset = updater.latest_full_asset()
    assert asset["tag"] == "v7.2.0"
    assert asset["name"] == "teyvat-full-v7.2.0.tar.gz"
    assert asset["size"] == 20



def test_refresh_russian_labels_preserves_cached_local_icons(tmp_path, monkeypatch):
    labels = [
        {"id": 1, "name": "传送点", "icon": "icons/root.webp",
         "children": [{"id": 2, "name": "宝箱", "icon": "icons/chest.webp"}]}
    ]
    (tmp_path / "labels.json").write_text(json.dumps(labels), encoding="utf-8")
    russian = {
        "retcode": 0,
        "data": {"tree": [
            {"id": 1, "name": "Точки телепортации", "icon": "https://cdn/root",
             "children": [{"id": 2, "name": "Сундук", "icon": "https://cdn/chest"}]}
        ]},
    }

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return json.dumps(russian, ensure_ascii=False).encode("utf-8")

    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    assert updater.refresh_russian_labels(tmp_path) == "ru-ru"
    saved = json.loads((tmp_path / "labels.json").read_text(encoding="utf-8"))
    assert saved[0]["name"] == "Точки телепортации"
    assert saved[0]["icon"] == "icons/root.webp"
    assert saved[0]["children"][0]["icon"] == "icons/chest.webp"


def test_refresh_russian_labels_falls_back_when_endpoint_returns_chinese(tmp_path, monkeypatch):
    (tmp_path / "labels.json").write_text(
        json.dumps([{"id": 1, "name": "宝箱", "icon": "icons/chest.webp"}]),
        encoding="utf-8",
    )

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            payload = {"retcode": 0, "data": {"tree": [{"id": 1, "name": "宝箱"}]}}
            return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    assert updater.refresh_russian_labels(tmp_path) == "zh-cn"
    saved = json.loads((tmp_path / "labels.json").read_text(encoding="utf-8"))
    assert saved[0]["name"] == "宝箱"
