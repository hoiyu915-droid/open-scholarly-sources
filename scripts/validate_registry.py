#!/usr/bin/env python3
"""Validate the canonical open-scholarly-sources registry without third-party packages."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "sources.json"
SCHEMA_PATH = ROOT / "schemas" / "source.schema.json"

SOURCE_TYPES = {
    "journal",
    "journal_collection",
    "publisher_platform",
    "institutional_repository",
    "subject_repository",
    "government_repository",
    "preprint_server",
    "aggregator",
    "directory",
    "digital_library",
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
    "id",
    "name",
    "organization",
    "source_type",
    "subjects",
    "oa_scope",
    "peer_review_scope",
    "publication_state",
    "canonical_url",
    "parent_id",
    "access_roles",
    "machine_access",
    "status",
    "verification",
    "notes",
}
OPTIONAL_SOURCE_KEYS = {"members", "transition"}
MACHINE_KEYS = {"formats", "feed_url", "api_url", "oai_pmh_url", "bulk_metadata_url"}
VERIFICATION_KEYS = {"status", "checked", "evidence_url"}
TRANSITION_KEYS = {"effective", "from", "to", "evidence_url"}


def load_json(path: Path):
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
    except ValueError:
        return False
    return True


def unique_strings(value) -> bool:
    return (
        isinstance(value, list)
        and all(isinstance(item, str) and item for item in value)
        and len(value) == len(set(value))
    )


def main() -> int:
    # Parse the schema as part of CI so a malformed contract never lands.
    load_json(SCHEMA_PATH)
    registry = load_json(DATA_PATH)
    errors: list[str] = []

    if not isinstance(registry, dict):
        errors.append("registry root must be an object")
        registry = {}

    if set(registry) != {"schema_version", "updated", "sources"}:
        errors.append("registry root must contain exactly schema_version, updated, sources")

    if not VERSION_RE.fullmatch(str(registry.get("schema_version", ""))):
        errors.append("schema_version must be semantic x.y.z")
    if not valid_date(registry.get("updated")):
        errors.append("updated must be an ISO date")

    sources = registry.get("sources")
    if not isinstance(sources, list):
        errors.append("sources must be an array")
        sources = []

    seen_ids: set[str] = set()
    parent_refs: list[tuple[str, str]] = []

    for index, source in enumerate(sources):
        label = f"sources[{index}]"
        if not isinstance(source, dict):
            errors.append(f"{label}: source must be an object")
            continue

        source_id = source.get("id", f"#{index}")
        label = str(source_id)
        keys = set(source)
        missing = REQUIRED_SOURCE_KEYS - keys
        unknown = keys - REQUIRED_SOURCE_KEYS - OPTIONAL_SOURCE_KEYS
        if missing:
            errors.append(f"{label}: missing keys {sorted(missing)}")
        if unknown:
            errors.append(f"{label}: unknown keys {sorted(unknown)}")

        if not isinstance(source_id, str) or not ID_RE.fullmatch(source_id):
            errors.append(f"{label}: invalid id")
        elif source_id in seen_ids:
            errors.append(f"{label}: duplicate id")
        else:
            seen_ids.add(source_id)

        for field in ("name", "organization"):
            if not isinstance(source.get(field), str) or not source[field].strip():
                errors.append(f"{label}: {field} must be a non-empty string")

        if source.get("source_type") not in SOURCE_TYPES:
            errors.append(f"{label}: invalid source_type")
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

        parent_id = source.get("parent_id")
        if parent_id is not None:
            if not isinstance(parent_id, str) or not ID_RE.fullmatch(parent_id):
                errors.append(f"{label}: invalid parent_id")
            else:
                parent_refs.append((label, parent_id))

        members = source.get("members")
        if members is not None and (not unique_strings(members) or not members):
            errors.append(f"{label}: members must be a non-empty unique string array")

        roles = source.get("access_roles")
        if not unique_strings(roles) or not roles:
            errors.append(f"{label}: access_roles must be a non-empty unique string array")
        elif any(role not in ACCESS_ROLES for role in roles):
            errors.append(f"{label}: invalid access role")
        else:
            if source.get("oa_scope") == "metadata_only" and set(roles) - {"discovery", "metadata", "abstract"}:
                errors.append(f"{label}: metadata_only source cannot claim hosted full text or canonical VOR")
            if source.get("publication_state") == "preprint" and "canonical_vor" in roles:
                errors.append(f"{label}: preprint source cannot claim canonical_vor")

        machine = source.get("machine_access")
        if not isinstance(machine, dict):
            errors.append(f"{label}: machine_access must be an object")
        else:
            if set(machine) != MACHINE_KEYS:
                errors.append(f"{label}: machine_access keys must be {sorted(MACHINE_KEYS)}")
            formats = machine.get("formats")
            if not unique_strings(formats):
                errors.append(f"{label}: machine formats must be a unique string array")
            elif any(fmt not in FORMATS for fmt in formats):
                errors.append(f"{label}: unsupported machine format")
            for field in ("feed_url", "api_url", "oai_pmh_url", "bulk_metadata_url"):
                value = machine.get(field)
                if value is not None and not is_https(value):
                    errors.append(f"{label}: {field} must be null or HTTPS")

        verification = source.get("verification")
        if not isinstance(verification, dict):
            errors.append(f"{label}: verification must be an object")
        else:
            if set(verification) != VERIFICATION_KEYS:
                errors.append(f"{label}: verification keys must be {sorted(VERIFICATION_KEYS)}")
            if verification.get("status") not in VERIFICATION_STATUSES:
                errors.append(f"{label}: invalid verification status")
            if not valid_date(verification.get("checked")):
                errors.append(f"{label}: verification.checked must be an ISO date")
            if not is_https(verification.get("evidence_url")):
                errors.append(f"{label}: verification.evidence_url must be HTTPS")

        transition = source.get("transition")
        if transition is not None:
            if not isinstance(transition, dict):
                errors.append(f"{label}: transition must be an object")
            else:
                if set(transition) != TRANSITION_KEYS:
                    errors.append(f"{label}: transition keys must be {sorted(TRANSITION_KEYS)}")
                for field in ("effective", "from", "to"):
                    if not isinstance(transition.get(field), str) or not transition[field].strip():
                        errors.append(f"{label}: transition.{field} must be a non-empty string")
                if not is_https(transition.get("evidence_url")):
                    errors.append(f"{label}: transition.evidence_url must be HTTPS")

        if not isinstance(source.get("notes"), str):
            errors.append(f"{label}: notes must be a string")

    for label, parent_id in parent_refs:
        if parent_id not in seen_ids:
            errors.append(f"{label}: parent_id {parent_id!r} does not exist")

    if errors:
        print(f"Registry validation failed with {len(errors)} error(s):", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    oa_counts = Counter(source["oa_scope"] for source in sources)
    type_counts = Counter(source["source_type"] for source in sources)
    print(
        "Registry OK: "
        f"{len(sources)} sources; "
        f"OA full={oa_counts['full']}, mixed={oa_counts['mixed']}, metadata_only={oa_counts['metadata_only']}; "
        f"journals={type_counts['journal']}, collections={type_counts['journal_collection']}, repositories={sum(type_counts[k] for k in ('institutional_repository', 'subject_repository', 'government_repository', 'digital_library'))}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
