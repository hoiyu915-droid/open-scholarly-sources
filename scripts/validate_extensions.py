#!/usr/bin/env python3
"""Validate manifest-defined registry shards and zh-TW bilingual coverage."""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MANIFEST_PATH = DATA / "registry-manifest.json"
SCHEMA_PATH = ROOT / "schemas" / "source.schema.json"

SOURCE_TYPES = {
    "journal", "journal_collection", "publisher_platform", "institutional_repository",
    "subject_repository", "government_repository", "preprint_server", "aggregator",
    "directory", "digital_library", "proceedings_platform", "proceedings_series", "review_platform",
}
OA_SCOPES = {"full", "mixed", "metadata_only", "unknown"}
PEER_REVIEW_SCOPES = {"peer_reviewed", "mixed", "not_peer_reviewed", "not_applicable", "unknown"}
PUBLICATION_STATES = {"published", "preprint", "mixed", "not_applicable"}
ACCESS_ROLES = {"discovery", "metadata", "abstract", "fulltext", "canonical_vor", "repository_copy"}
FORMATS = {"html", "pdf", "xml", "json", "csv", "rdf"}
STATUSES = {"active", "inactive", "migrating", "unknown"}
VERIFICATION_STATUSES = {"verified", "partial", "needs_review"}
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")

REQUIRED_SOURCE_KEYS = {
    "id", "name", "organization", "source_type", "subjects", "oa_scope",
    "peer_review_scope", "publication_state", "canonical_url", "parent_id",
    "access_roles", "machine_access", "status", "verification", "notes",
}
OPTIONAL_SOURCE_KEYS = {"members", "transition"}
MACHINE_KEYS = {"formats", "feed_url", "api_url", "oai_pmh_url", "bulk_metadata_url"}
VERIFICATION_KEYS = {"status", "checked", "evidence_url"}


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"missing file: {path.relative_to(ROOT)}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")


def is_https(value) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def valid_date(value) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def unique_strings(value) -> bool:
    return isinstance(value, list) and all(isinstance(x, str) and x for x in value) and len(value) == len(set(value))


def validate_source(source, label: str, errors: list[str]) -> None:
    if not isinstance(source, dict):
        errors.append(f"{label}: source must be an object")
        return

    keys = set(source)
    missing = REQUIRED_SOURCE_KEYS - keys
    unknown = keys - REQUIRED_SOURCE_KEYS - OPTIONAL_SOURCE_KEYS
    if missing:
        errors.append(f"{label}: missing keys {sorted(missing)}")
    if unknown:
        errors.append(f"{label}: unknown keys {sorted(unknown)}")

    sid = source.get("id")
    if not isinstance(sid, str) or not ID_RE.fullmatch(sid):
        errors.append(f"{label}: invalid id")
    for field in ("name", "organization"):
        if not isinstance(source.get(field), str) or not source[field].strip():
            errors.append(f"{label}: {field} must be non-empty")

    if source.get("source_type") not in SOURCE_TYPES:
        errors.append(f"{label}: invalid source_type {source.get('source_type')!r}")
    if source.get("oa_scope") not in OA_SCOPES:
        errors.append(f"{label}: invalid oa_scope")
    if source.get("peer_review_scope") not in PEER_REVIEW_SCOPES:
        errors.append(f"{label}: invalid peer_review_scope")
    if source.get("publication_state") not in PUBLICATION_STATES:
        errors.append(f"{label}: invalid publication_state")
    if source.get("status") not in STATUSES:
        errors.append(f"{label}: invalid status")

    if not unique_strings(source.get("subjects")) or not source.get("subjects"):
        errors.append(f"{label}: subjects must be a non-empty unique string array")
    if not is_https(source.get("canonical_url")):
        errors.append(f"{label}: canonical_url must be HTTPS")

    parent = source.get("parent_id")
    if parent is not None and (not isinstance(parent, str) or not ID_RE.fullmatch(parent)):
        errors.append(f"{label}: invalid parent_id")

    roles = source.get("access_roles")
    if not unique_strings(roles) or not roles or any(role not in ACCESS_ROLES for role in (roles or [])):
        errors.append(f"{label}: invalid access_roles")
    elif source.get("publication_state") == "preprint" and "canonical_vor" in roles:
        errors.append(f"{label}: preprint cannot claim canonical_vor")

    machine = source.get("machine_access")
    if not isinstance(machine, dict) or set(machine) != MACHINE_KEYS:
        errors.append(f"{label}: invalid machine_access object")
    else:
        formats = machine.get("formats")
        if not unique_strings(formats) or any(fmt not in FORMATS for fmt in (formats or [])):
            errors.append(f"{label}: invalid machine formats")
        for field in ("feed_url", "api_url", "oai_pmh_url", "bulk_metadata_url"):
            value = machine.get(field)
            if value is not None and not is_https(value):
                errors.append(f"{label}: {field} must be null or HTTPS")

    verification = source.get("verification")
    if not isinstance(verification, dict) or set(verification) != VERIFICATION_KEYS:
        errors.append(f"{label}: invalid verification object")
    else:
        if verification.get("status") not in VERIFICATION_STATUSES:
            errors.append(f"{label}: invalid verification status")
        if not valid_date(verification.get("checked")):
            errors.append(f"{label}: invalid verification date")
        if not is_https(verification.get("evidence_url")):
            errors.append(f"{label}: verification evidence must be HTTPS")

    if not isinstance(source.get("notes"), str):
        errors.append(f"{label}: notes must be a string")


def main() -> int:
    errors: list[str] = []
    load(SCHEMA_PATH)
    manifest = load(MANIFEST_PATH)

    expected_manifest_keys = {"schema_version", "updated", "source_shards", "translations"}
    if not isinstance(manifest, dict) or set(manifest) != expected_manifest_keys:
        errors.append("manifest: invalid root keys")
        manifest = {}
    if not VERSION_RE.fullmatch(str(manifest.get("schema_version", ""))):
        errors.append("manifest: invalid schema_version")
    if not valid_date(manifest.get("updated")):
        errors.append("manifest: invalid updated date")

    shard_names = manifest.get("source_shards")
    if not unique_strings(shard_names) or not shard_names:
        errors.append("manifest: source_shards must be a non-empty unique string array")
        shard_names = []
    elif "sources.json" not in shard_names:
        errors.append("manifest: sources.json must remain the base shard")

    sources: list[dict] = []
    for shard_name in shard_names:
        if Path(shard_name).name != shard_name or not shard_name.startswith("sources") or not shard_name.endswith(".json"):
            errors.append(f"manifest: invalid shard name {shard_name!r}")
            continue
        registry = load(DATA / shard_name)
        if not isinstance(registry, dict) or set(registry) != {"schema_version", "updated", "sources"}:
            errors.append(f"{shard_name}: invalid registry root")
            continue
        if not VERSION_RE.fullmatch(str(registry.get("schema_version", ""))):
            errors.append(f"{shard_name}: invalid schema_version")
        if not valid_date(registry.get("updated")):
            errors.append(f"{shard_name}: invalid updated date")
        if not isinstance(registry.get("sources"), list):
            errors.append(f"{shard_name}: sources must be an array")
            continue
        sources.extend(registry["sources"])

    seen: set[str] = set()
    for idx, source in enumerate(sources):
        sid = source.get("id", f"#{idx}") if isinstance(source, dict) else f"#{idx}"
        validate_source(source, str(sid), errors)
        if isinstance(sid, str):
            if sid in seen:
                errors.append(f"{sid}: duplicate id across shards")
            seen.add(sid)

    for source in sources:
        if isinstance(source, dict) and source.get("parent_id") is not None and source["parent_id"] not in seen:
            errors.append(f"{source.get('id')}: parent_id {source['parent_id']!r} does not exist")

    translation_name = manifest.get("translations")
    if not isinstance(translation_name, str) or Path(translation_name).name != translation_name:
        errors.append("manifest: invalid translations filename")
        i18n = {}
    else:
        i18n = load(DATA / translation_name)

    if not isinstance(i18n, dict) or set(i18n) != {"locale", "updated", "taxonomy", "sources"}:
        errors.append("i18n: invalid root keys")
    else:
        if i18n.get("locale") != "zh-TW":
            errors.append("i18n: locale must be zh-TW")
        if not valid_date(i18n.get("updated")):
            errors.append("i18n: invalid updated date")
        translations = i18n.get("sources")
        if not isinstance(translations, dict):
            errors.append("i18n: sources must be an object")
            translations = {}
        translated_ids = set(translations)
        if translated_ids != seen:
            missing = sorted(seen - translated_ids)
            unknown = sorted(translated_ids - seen)
            if missing:
                errors.append(f"i18n: missing source translations {missing}")
            if unknown:
                errors.append(f"i18n: unknown source translations {unknown}")
        for sid, item in translations.items():
            if not isinstance(item, dict) or set(item) != {"name", "summary"}:
                errors.append(f"i18n {sid}: expected exactly name and summary")
                continue
            if any(not isinstance(item.get(k), str) or not item[k].strip() for k in ("name", "summary")):
                errors.append(f"i18n {sid}: empty name or summary")

        taxonomy = i18n.get("taxonomy")
        required_taxonomies = {
            "subjects": {x for s in sources if isinstance(s, dict) for x in s.get("subjects", [])},
            "source_types": {s.get("source_type") for s in sources if isinstance(s, dict)},
            "oa_scopes": {s.get("oa_scope") for s in sources if isinstance(s, dict)},
            "peer_review_scopes": {s.get("peer_review_scope") for s in sources if isinstance(s, dict)},
            "publication_states": {s.get("publication_state") for s in sources if isinstance(s, dict)},
            "access_roles": {x for s in sources if isinstance(s, dict) for x in s.get("access_roles", [])},
            "verification_status": {s.get("verification", {}).get("status") for s in sources if isinstance(s, dict)},
        }
        if not isinstance(taxonomy, dict):
            errors.append("i18n: taxonomy must be an object")
        else:
            for group, values in required_taxonomies.items():
                mapping = taxonomy.get(group)
                if not isinstance(mapping, dict):
                    errors.append(f"i18n taxonomy: missing group {group}")
                    continue
                missing = sorted(v for v in values if v and v not in mapping)
                if missing:
                    errors.append(f"i18n taxonomy {group}: missing {missing}")

    if errors:
        print(f"Extension validation failed with {len(errors)} error(s):", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print(f"Extensions OK: shards={len(shard_names)}, sources={len(sources)}, zh-TW translations={len(i18n['sources'])}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
