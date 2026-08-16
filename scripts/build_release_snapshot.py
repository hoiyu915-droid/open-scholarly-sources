#!/usr/bin/env python3
"""Finalize machine outputs with release identity and stage immutable snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

DEFAULT_BASE_URL = "https://hoiyu915-droid.github.io/open-scholarly-sources"
DEFAULT_REPOSITORY = "hoiyu915-droid/open-scholarly-sources"
RELEASE_ID_RE = re.compile(r"^[0-9a-f]{40}$")
SNAPSHOT_FILES = (
    "registry.json",
    "registry.ndjson",
    "registry.jsonld",
    "source-profiles.json",
    "source-profiles.ndjson",
    "llms.txt",
    "llms-full.txt",
)
SCHEMA_FILES = (
    "source.schema.json",
    "source-profile.schema.json",
    "release-manifest.schema.json",
)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_meta(path: Path, url: str, mutable_url: str | None = None):
    out = {"sha256": sha256(path), "bytes": path.stat().st_size, "url": url}
    if mutable_url:
        out["mutable_url"] = mutable_url
    return out


def release_identity(
    release_id: str,
    commit_sha: str,
    release_date: str,
    base_url: str,
    repository: str,
):
    immutable_base = f"{base_url}/releases/{release_id}"
    return {
        "schema_version": "1.0.0",
        "release_id": release_id,
        "commit_sha": commit_sha,
        "release_date": release_date,
        "commit_url": f"https://github.com/{repository}/commit/{commit_sha}",
        "repository_main_ref_api": f"https://api.github.com/repos/{repository}/git/ref/heads/main",
        "mutable_base": base_url + "/",
        "immutable_base": immutable_base + "/",
        "manifest_url": f"{immutable_base}/release-manifest.json",
        "mutable_manifest_url": f"{base_url}/release-manifest.json",
    }


def stamp_homepage(site: Path, identity: dict) -> None:
    path = site / "index.html"
    if not path.is_file():
        raise SystemExit("homepage missing before release stamping")
    text = path.read_text(encoding="utf-8")

    meta = (
        f'  <meta name="oss-release-id" content="{identity["release_id"]}">\n'
        f'  <link rel="alternate" type="application/json" href="./release-manifest.json" title="Release manifest">\n'
    )
    if 'name="oss-release-id"' not in text:
        text = text.replace("</head>", meta + "</head>", 1)

    link = '<a href="./release-manifest.json">Release manifest / 發布識別</a>'
    if link not in text:
        marker = '<a href="./llms.txt">llms.txt</a>'
        if marker in text:
            text = text.replace(marker, marker + "\n    " + link, 1)

    notice = (
        '<div class="notice" id="release-identity"><strong>Release identity / 發布識別：</strong> '
        f'<code>{identity["release_id"]}</code> · '
        f'<a href="./release-manifest.json">manifest</a> · '
        f'<a href="./releases/{identity["release_id"]}/release-manifest.json">immutable snapshot</a>. '
        'Mutable latest URLs may briefly return an older release through intermediary caches; '
        'compare this release ID with the repository main ref when freshness matters. '
        '可變 latest URL 可能因中介快取短暫回傳舊版；需要最新狀態時請核對 release ID 與 main ref。</div>\n  '
    )
    if 'id="release-identity"' not in text:
        marker = '<main class="wrap">\n  '
        if marker not in text:
            raise SystemExit("homepage main marker missing")
        text = text.replace(marker, marker + notice, 1)

    path.write_text(text, encoding="utf-8")


def inject_identity(site: Path, identity: dict) -> tuple[int, str, str]:
    registry_path = site / "registry.json"
    profiles_path = site / "source-profiles.json"
    jsonld_path = site / "registry.jsonld"

    registry = read_json(registry_path)
    registry["release"] = identity
    write_json(registry_path, registry)

    profiles = read_json(profiles_path)
    profiles["release"] = identity
    write_json(profiles_path, profiles)

    jsonld = read_json(jsonld_path)
    jsonld["version"] = identity["release_id"]
    jsonld["isBasedOn"] = identity["commit_url"]
    write_json(jsonld_path, jsonld)

    banner = (
        f"Release identity: {identity['release_id']}\n"
        f"Repository commit: {identity['commit_url']}\n"
        f"Immutable snapshot: {identity['immutable_base']}\n"
        f"Release manifest: {identity['manifest_url']}\n"
        f"Release history: {identity['mutable_base']}releases/index.json\n"
        "Freshness note: mutable endpoints may be temporarily stale because of intermediary caching or propagation. "
        "Compare the release identity with the repository main ref when freshness matters.\n"
    )
    for name in ("llms.txt", "llms-full.txt"):
        path = site / name
        text = path.read_text(encoding="utf-8")
        if "Release identity:" not in text:
            first, separator, rest = text.partition("\n")
            text = first + "\n\n" + banner + ("\n" + rest if separator else "")
            path.write_text(text, encoding="utf-8")

    stamp_homepage(site, identity)

    # NDJSON intentionally remains one source record per line. Pair it with
    # release-manifest.json or use its commit-addressed immutable URL.
    return registry["source_count"], profiles["schema_version"], profiles["method"]


def copy_existing_archive(site: Path, archive_root: Path | None) -> None:
    releases = site / "releases"
    releases.mkdir(parents=True, exist_ok=True)
    if not archive_root or not archive_root.exists():
        return
    for child in archive_root.iterdir():
        destination = releases / child.name
        if child.is_dir():
            if destination.exists():
                continue
            shutil.copytree(child, destination)
        elif child.is_file() and child.name == "index.json":
            shutil.copy2(child, destination)


def stage_snapshot(
    site: Path,
    identity: dict,
    source_count: int,
    profile_schema: str,
    profile_method: str,
) -> dict:
    release_id = identity["release_id"]
    releases = site / "releases"
    snapshot = releases / release_id
    immutable_base = identity["immutable_base"].rstrip("/")

    if snapshot.exists():
        existing_path = snapshot / "release-manifest.json"
        if not existing_path.exists():
            raise SystemExit(f"existing release directory lacks manifest: {snapshot}")
        existing = read_json(existing_path)
        if existing.get("release_id") != release_id or existing.get("commit_sha") != identity["commit_sha"]:
            raise SystemExit(f"immutable release conflict: {release_id}")
        return existing

    snapshot.mkdir(parents=True)
    files = {}
    for name in SNAPSHOT_FILES:
        source = site / name
        if not source.is_file():
            raise SystemExit(f"missing machine output before release snapshot: {name}")
        destination = snapshot / name
        shutil.copy2(source, destination)
        files[name] = file_meta(
            destination,
            f"{immutable_base}/{name}",
            f"{identity['mutable_base']}{name}",
        )

    schema_dir = snapshot / "schemas"
    schema_dir.mkdir()
    for name in SCHEMA_FILES:
        source = site / "schemas" / name
        if not source.is_file():
            raise SystemExit(f"missing schema before release snapshot: schemas/{name}")
        destination = schema_dir / name
        shutil.copy2(source, destination)
        key = f"schemas/{name}"
        files[key] = file_meta(
            destination,
            f"{immutable_base}/{key}",
            f"{identity['mutable_base']}schemas/{name}",
        )

    manifest = {
        "$schema": f"{immutable_base}/schemas/release-manifest.schema.json",
        **identity,
        "source_count": source_count,
        "profile_schema_version": profile_schema,
        "profile_method": profile_method,
        "files": files,
        "consistency_contract": {
            "mutable_endpoints": "latest deployed convenience URLs; intermediary caches may temporarily return an older release",
            "immutable_endpoints": "content for this release ID must not change; compare SHA-256 digests before trusting a conflicting copy",
            "freshness_check": "compare commit_sha with repository_main_ref_api when current-main freshness matters",
            "ndjson_identity": "pair registry.ndjson or source-profiles.ndjson with this manifest; NDJSON remains one record per line",
        },
    }
    write_json(snapshot / "release-manifest.json", manifest)
    return manifest


def update_release_index(site: Path, manifest: dict) -> None:
    releases = site / "releases"
    index_path = releases / "index.json"
    if index_path.exists():
        index = read_json(index_path)
        entries = index.get("releases", [])
    else:
        entries = []

    by_id = {entry["release_id"]: entry for entry in entries if "release_id" in entry}
    release_id = manifest["release_id"]
    by_id[release_id] = {
        "release_id": release_id,
        "commit_sha": manifest["commit_sha"],
        "release_date": manifest["release_date"],
        "source_count": manifest["source_count"],
        "profile_schema_version": manifest["profile_schema_version"],
        "profile_method": manifest["profile_method"],
        "manifest_url": manifest["manifest_url"],
        "immutable_base": manifest["immutable_base"],
    }
    ordered = sorted(by_id.values(), key=lambda item: (item["release_date"], item["release_id"]))
    write_json(
        index_path,
        {
            "schema_version": "1.0.0",
            "current_release_id": release_id,
            "releases": ordered,
        },
    )


def verify_manifest(site: Path, manifest: dict) -> None:
    snapshot = site / "releases" / manifest["release_id"]
    for name, metadata in manifest["files"].items():
        path = snapshot / name
        if not path.is_file():
            raise SystemExit(f"release snapshot missing file: {name}")
        actual = sha256(path)
        if actual != metadata["sha256"]:
            raise SystemExit(
                f"release digest mismatch for {name}: {actual} != {metadata['sha256']}"
            )

    registry_release = read_json(site / "registry.json")["release"]["release_id"]
    profile_release = read_json(site / "source-profiles.json")["release"]["release_id"]
    if registry_release != manifest["release_id"] or profile_release != manifest["release_id"]:
        raise SystemExit("mutable machine output release identity mismatch")
    homepage = (site / "index.html").read_text(encoding="utf-8")
    if manifest["release_id"] not in homepage or "release-manifest.json" not in homepage:
        raise SystemExit("homepage release identity missing")


def build(
    site: Path,
    archive_root: Path | None,
    release_id: str,
    commit_sha: str,
    release_date: str,
    base_url: str,
    repository: str,
) -> None:
    if not RELEASE_ID_RE.fullmatch(release_id) or not RELEASE_ID_RE.fullmatch(commit_sha):
        raise SystemExit("release-id and commit-sha must be full 40-character lowercase hex SHAs")
    if release_id != commit_sha:
        raise SystemExit("release-id must equal commit-sha for this contract")

    identity = release_identity(
        release_id,
        commit_sha,
        release_date,
        base_url.rstrip("/"),
        repository,
    )
    copy_existing_archive(site, archive_root)
    source_count, profile_schema, profile_method = inject_identity(site, identity)
    manifest = stage_snapshot(site, identity, source_count, profile_schema, profile_method)
    write_json(site / "release-manifest.json", manifest)
    update_release_index(site, manifest)
    verify_manifest(site, manifest)

    print(
        f"Release snapshot OK: release={release_id}, sources={source_count}, "
        f"profile_rules={profile_schema}, files={len(manifest['files'])}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--archive-root", type=Path)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--release-date", required=True)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    args = parser.parse_args()
    build(
        args.site,
        args.archive_root,
        args.release_id,
        args.commit_sha,
        args.release_date,
        args.base_url,
        args.repository,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
