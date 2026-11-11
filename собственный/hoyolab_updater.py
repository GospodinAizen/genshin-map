"""Download and atomically install the latest public HoYoLAB Teyvat snapshot.

The upstream release archive is kept in the user's cache, never committed to git.
Only GitHub's public release metadata and its declared full-snapshot asset are used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any

from hoyolab_importer import import_snapshot
from hoyolab_runtime import build_runtime_assets

RELEASE_API = "https://api.github.com/repos/kxxoling/genshin-map-data/releases/latest"
MAX_ARCHIVE_BYTES = 300 * 1024 * 1024
MAX_EXTRACTED_BYTES = 1024 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 100_000
USER_AGENT = "GenshinMapOverlay/0.1 (public snapshot updater)"


def _request(url: str, *, accept: str = "application/vnd.github+json"):
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": accept}
    )
    return urllib.request.urlopen(request, timeout=60)


def latest_full_asset() -> dict[str, Any]:
    with _request(RELEASE_API) as response:
        release = json.loads(response.read().decode("utf-8"))
    tag = release.get("tag_name")
    expected = f"teyvat-full-{tag}.tar.gz"
    assets = [a for a in release.get("assets", []) if a.get("name") == expected]
    if len(assets) != 1:
        raise RuntimeError(f"Release {tag!r} does not contain exactly one {expected!r} asset.")
    asset = assets[0]
    if not asset.get("browser_download_url") or not asset.get("size"):
        raise RuntimeError("The full snapshot asset metadata is incomplete.")
    if int(asset["size"]) > MAX_ARCHIVE_BYTES:
        raise RuntimeError(f"Snapshot archive exceeds the {MAX_ARCHIVE_BYTES}-byte safety limit.")
    return {
        "tag": tag,
        "name": expected,
        "url": asset["browser_download_url"],
        "size": int(asset["size"]),
        "digest": asset.get("digest"),
        "published_at": release.get("published_at"),
        "html_url": release.get("html_url"),
    }


def download_asset(asset: dict[str, Any], destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    total = 0
    fd, temporary_name = tempfile.mkstemp(prefix="snapshot-", suffix=".part", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as output, _request(asset["url"], accept="application/octet-stream") as response:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_ARCHIVE_BYTES:
                    raise RuntimeError("Downloaded archive exceeded the safety size limit.")
                digest.update(chunk)
                output.write(chunk)
        if total != asset["size"]:
            raise RuntimeError(f"Archive size mismatch: expected {asset['size']}, received {total}.")
        actual = digest.hexdigest()
        declared = asset.get("digest")
        if declared:
            algorithm, _, expected = declared.partition(":")
            if algorithm != "sha256" or actual.lower() != expected.lower():
                raise RuntimeError("Snapshot archive SHA-256 does not match the release digest.")
        os.replace(temporary_name, destination)
        return actual
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def safe_extract(archive_path: Path, destination: Path) -> Path:
    """Extract regular files only; reject traversal, links, devices and oversized archives."""
    destination.mkdir(parents=True, exist_ok=True)
    total_size = 0
    members_seen = 0
    with tarfile.open(archive_path, mode="r:gz") as archive:
        for member in archive:
            members_seen += 1
            if members_seen > MAX_ARCHIVE_MEMBERS:
                raise RuntimeError("Archive contains too many entries.")
            relative = PurePosixPath(member.name)
            if relative.is_absolute() or not relative.parts or any(p in ("", ".", "..") for p in relative.parts):
                raise RuntimeError(f"Unsafe archive path: {member.name!r}")
            if not (member.isdir() or member.isfile()) or member.issym() or member.islnk():
                raise RuntimeError(f"Unsupported archive entry type: {member.name!r}")
            if member.size < 0:
                raise RuntimeError(f"Invalid archive member size: {member.name!r}")
            total_size += member.size
            if total_size > MAX_EXTRACTED_BYTES:
                raise RuntimeError("Extracted archive exceeds the safety size limit.")
            target = destination.joinpath(*relative.parts)
            resolved_root = destination.resolve()
            resolved_target = target.resolve()
            if resolved_target != resolved_root and resolved_root not in resolved_target.parents:
                raise RuntimeError(f"Archive path escapes extraction directory: {member.name!r}")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise RuntimeError(f"Cannot read archive member: {member.name!r}")
            with source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
    candidates = [p.parent for p in destination.rglob("meta.json")
                  if (p.parent / "labels.json").is_file() and (p.parent / "points.json").is_file()]
    if len(candidates) != 1:
        raise RuntimeError("Archive must contain exactly one directory with meta.json, labels.json and points.json.")
    return candidates[0]


def install_latest(cache_dir: Path, *, force: bool = False, map_key: str = "teyvat_surface") -> dict[str, Any]:
    asset = latest_full_asset()
    target = cache_dir / "teyvat"
    version_file = target / "upstream-release.json"
    if not force and version_file.is_file():
        try:
            installed = json.loads(version_file.read_text(encoding="utf-8"))
            runtime_ready = (
                (target / "markers.runtime.json").is_file()
                and (target / "references" / "manifest.json").is_file()
                and (target / "references" / "teyvat_world_zoom_minus4.png").is_file()
            )
            if installed.get("tag") == asset["tag"] and runtime_ready:
                return {"status": "current", "tag": asset["tag"], "path": str(target)}
        except (OSError, json.JSONDecodeError):
            pass

    cache_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hoyolab-update-", dir=cache_dir) as temp:
        work = Path(temp)
        archive_path = work / asset["name"]
        archive_sha = download_asset(asset, archive_path)
        extracted = safe_extract(archive_path, work / "extracted")
        normalized = import_snapshot(extracted, map_key=map_key)
        if normalized["point_count"] < 1000:
            raise RuntimeError(f"Snapshot validation failed: only {normalized['point_count']} known points.")
        (extracted / "markers.normalized.json").write_text(
            json.dumps(normalized, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        metadata = {**{k: asset[k] for k in ("tag", "name", "published_at", "html_url")},
                    "archive_sha256": archive_sha, "map_key": map_key,
                    "point_count": normalized["point_count"]}
        (extracted / "upstream-release.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        runtime = build_runtime_assets(extracted)
        metadata["runtime"] = runtime
        (extracted / "upstream-release.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        backup = cache_dir / "teyvat.previous"
        if backup.exists():
            shutil.rmtree(backup)
        if target.exists():
            os.replace(target, backup)
        try:
            os.replace(extracted, target)
        except Exception:
            if backup.exists() and not target.exists():
                os.replace(backup, target)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    return {"status": "installed", "tag": asset["tag"], "path": str(target),
            "point_count": normalized["point_count"], "archive_sha256": archive_sha}


def default_cache_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "genshin-map-overlay" / "hoyolab"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=default_cache_dir())
    parser.add_argument("--check", action="store_true", help="Show latest upstream version without downloading.")
    parser.add_argument("--force", action="store_true", help="Reinstall even if this release is already cached.")
    parser.add_argument("--map-key", default="teyvat_surface")
    args = parser.parse_args()
    if args.check:
        asset = latest_full_asset()
        print(json.dumps({k: asset[k] for k in ("tag", "name", "size", "published_at", "html_url")},
                         ensure_ascii=False, indent=2))
        return 0
    result = install_latest(args.cache_dir, force=args.force, map_key=args.map_key)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
