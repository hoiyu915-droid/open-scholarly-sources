#!/usr/bin/env python3
"""Minimal executable reference consumer for the routing contract.

Scope v0.1:
- structured formal_evidence input only;
- candidate DOI resolution through Crossref;
- deterministic binding to a pinned registry source by normalized container title;
- registry source-scope attestation;
- admissibility, coverage, and public-ocean eligibility verdicts.

This module intentionally does not classify natural-language intent, infer peer
review from publisher prose, resolve OA/version state beyond registry facts, or
promote new sources into the canonical registry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "data" / "retrieval-routing-policy.json"
REGISTRY_MANIFEST_PATH = ROOT / "data" / "registry-manifest.json"
PROFILE_RULES_PATH = ROOT / "data" / "source-profile-rules.json"
TERMINAL_ATTEMPT_STATES = {
    "success_with_candidates",
    "success_empty",
    "failed_after_policy_budget",
    "not_applicable",
}
RELEASE_ID_RE = re.compile(r"^[0-9a-f]{40}$")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_json_bytes(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_title(value: str) -> str:
    text = value.casefold().strip()
    text = re.sub(r"\s*\([a-z0-9 .&/+\-]{2,16}\)\s*$", "", text)
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def load_registry() -> tuple[dict, dict[str, dict]]:
    manifest = load_json(REGISTRY_MANIFEST_PATH)
    by_id: dict[str, dict] = {}
    for filename in manifest["source_shards"]:
        shard = load_json(ROOT / "data" / filename)
        for source in shard["sources"]:
            if source["id"] in by_id:
                raise SystemExit(f"duplicate source id in registry: {source['id']}")
            by_id[source["id"]] = source
    return manifest, by_id


@dataclass
class ResolveResult:
    ok: bool
    message: dict | None
    response_sha256: str | None
    observed_at: str
    error: str | None = None


class CrossrefResolver:
    name = "crossref"
    method = "doi_record"

    def resolve(self, doi: str) -> ResolveResult:
        url = "https://api.crossref.org/works/" + quote(doi, safe="")
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "open-scholarly-sources-reference-consumer/0.1 (+https://github.com/hoiyu915-droid/open-scholarly-sources)",
            },
        )
        observed_at = utc_now()
        try:
            with urlopen(request, timeout=20) as response:
                raw = response.read()
        except HTTPError as exc:
            return ResolveResult(False, None, None, observed_at, f"http_{exc.code}")
        except URLError as exc:
            return ResolveResult(False, None, None, observed_at, f"network_error:{exc.reason}")
        payload = json.loads(raw.decode("utf-8"))
        message = payload.get("message")
        if not isinstance(message, dict):
            return ResolveResult(False, None, sha256_bytes(raw), observed_at, "missing_crossref_message")
        return ResolveResult(True, message, sha256_bytes(raw), observed_at)


class FixtureCrossrefResolver(CrossrefResolver):
    """Deterministic resolver used by conformance tests."""

    def __init__(self, path: Path):
        self.records = load_json(path)["records"]

    def resolve(self, doi: str) -> ResolveResult:
        observed_at = "2026-08-17T00:00:00Z"
        record = self.records.get(doi)
        if record is None:
            return ResolveResult(False, None, None, observed_at, "fixture_not_found")
        raw = canonical_json_bytes(record)
        return ResolveResult(True, record, sha256_bytes(raw), observed_at)


def crossref_container_titles(message: dict) -> list[str]:
    values = message.get("container-title", [])
    if isinstance(values, str):
        values = [values]
    return [value for value in values if isinstance(value, str) and value.strip()]


def bind_registry_source(message: dict, registry: dict[str, dict], source_hint: str | None):
    titles = crossref_container_titles(message)
    normalized_titles = {normalize_title(title) for title in titles}

    if source_hint:
        source = registry.get(source_hint)
        if source is None:
            return None, "source_hint_not_registered"
        if normalize_title(source["name"]) not in normalized_titles:
            return None, "source_hint_container_mismatch"
        return source, "crossref_container_title_normalized_exact"

    matches = [
        source
        for source in registry.values()
        if source["source_type"] == "journal" and normalize_title(source["name"]) in normalized_titles
    ]
    if len(matches) == 1:
        return matches[0], "crossref_container_title_normalized_exact"
    if len(matches) > 1:
        return None, "ambiguous_registry_container_match"
    return None, "no_registry_container_match"


def registry_source_scope(source: dict) -> tuple[bool, list[str]]:
    failures = []
    if source.get("verification", {}).get("status") != "verified":
        failures.append("source_not_verified")
    if source.get("peer_review_scope") != "peer_reviewed":
        failures.append("peer_review_scope_not_peer_reviewed")
    if source.get("publication_state") != "published":
        failures.append("publication_state_not_published")
    if "canonical_vor" not in source.get("access_roles", []):
        failures.append("canonical_vor_role_missing")
    if source.get("status") != "active":
        failures.append("source_not_active")
    return not failures, failures


def resolve_candidate(candidate: dict, registry: dict[str, dict], resolver: CrossrefResolver) -> dict:
    doi = candidate.get("doi")
    route = candidate.get("route", "registry_direct")
    if not isinstance(doi, str) or not doi.strip():
        return {
            "candidate": candidate,
            "admissibility": "unresolved",
            "reason": "missing_doi",
            "resolution_attestations": [],
            "fallback_depth": 2 if route == "public_ocean" else 0,
        }

    result = resolver.resolve(doi.strip())
    attestations = []
    fallback_depth = 2 if route == "public_ocean" else 0
    if not result.ok or not result.message:
        attestations.append(
            {
                "attestation_type": "document_identity",
                "status": "failed",
                "resolver": resolver.name,
                "method": resolver.method,
                "identifier": doi,
                "observed_at": result.observed_at,
                "error": result.error,
            }
        )
        return {
            "candidate": candidate,
            "admissibility": "unresolved",
            "reason": "document_identity_unresolved",
            "resolution_attestations": attestations,
            "fallback_depth": fallback_depth,
        }

    resolved_doi = str(result.message.get("DOI", "")).strip()
    if resolved_doi.casefold() != doi.strip().casefold():
        attestations.append(
            {
                "attestation_type": "document_identity",
                "status": "failed",
                "resolver": resolver.name,
                "method": resolver.method,
                "identifier": doi,
                "observed_at": result.observed_at,
                "response_sha256": result.response_sha256,
                "error": "doi_mismatch",
            }
        )
        return {
            "candidate": candidate,
            "admissibility": "unresolved",
            "reason": "crossref_doi_mismatch",
            "resolution_attestations": attestations,
            "fallback_depth": fallback_depth,
        }

    attestations.append(
        {
            "attestation_type": "document_identity",
            "status": "verified",
            "resolver": resolver.name,
            "method": resolver.method,
            "identifier": resolved_doi,
            "observed_at": result.observed_at,
            "response_sha256": result.response_sha256,
            "crossref_type": result.message.get("type"),
        }
    )

    source, binding_method = bind_registry_source(result.message, registry, candidate.get("source_hint"))
    if source is None:
        attestations.append(
            {
                "attestation_type": "container_identity",
                "status": "unknown",
                "resolver": "registry",
                "method": binding_method,
                "container_titles": crossref_container_titles(result.message),
            }
        )
        return {
            "candidate": candidate,
            "admissibility": "discovery_only",
            "reason": binding_method,
            "resolution_attestations": attestations,
            "fallback_depth": fallback_depth,
        }

    attestations.append(
        {
            "attestation_type": "container_identity",
            "status": "verified",
            "resolver": "registry",
            "method": binding_method,
            "source_id": source["id"],
            "container_titles": crossref_container_titles(result.message),
        }
    )

    scope_ok, failures = registry_source_scope(source)
    attestations.append(
        {
            "attestation_type": "registry_source_scope",
            "status": "verified" if scope_ok else "partial",
            "resolver": "registry",
            "method": "pinned_source_record",
            "source_id": source["id"],
            "peer_review_scope": source["peer_review_scope"],
            "publication_state": source["publication_state"],
            "canonical_vor": "canonical_vor" in source["access_roles"],
            "verification_evidence_url": source["verification"]["evidence_url"],
            "verification_checked": source["verification"]["checked"],
            "failures": failures,
        }
    )

    if scope_ok:
        return {
            "candidate": candidate,
            "source_id": source["id"],
            "admissibility": "formal_evidence",
            "reason": "crossref_identity_plus_registry_source_scope",
            "resolution_attestations": attestations,
            "fallback_depth": fallback_depth,
        }
    return {
        "candidate": candidate,
        "source_id": source["id"],
        "admissibility": "discovery_only",
        "reason": "registry_source_scope_incomplete",
        "resolution_attestations": attestations,
        "fallback_depth": fallback_depth,
    }


def execute(payload: dict, resolver: CrossrefResolver) -> dict:
    policy = load_json(POLICY_PATH)
    policy_bytes = POLICY_PATH.read_bytes()
    profile_rules = load_json(PROFILE_RULES_PATH)
    manifest, registry = load_registry()

    release_id = payload.get("registry_release_id")
    if not isinstance(release_id, str) or RELEASE_ID_RE.fullmatch(release_id) is None:
        raise SystemExit("registry_release_id must be a full 40-character lowercase hex commit SHA")

    query_envelope = payload.get("query_envelope", {})
    if query_envelope.get("mode") not in policy["modes"]:
        raise SystemExit("query_envelope.mode is not allowed by routing policy")
    requirements = query_envelope.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        raise SystemExit("query_envelope.requirements must be a non-empty list")
    unknown_requirements = sorted(set(requirements) - set(policy["requirements"]))
    if unknown_requirements:
        raise SystemExit(f"unknown requirements: {unknown_requirements}")
    if "formal_evidence" not in requirements:
        raise SystemExit("reference consumer v0.1 requires formal_evidence")

    route_attempts = payload.get("route_attempts", [])
    for attempt in route_attempts:
        if attempt.get("attempt_status") not in TERMINAL_ATTEMPT_STATES:
            raise SystemExit(f"non-terminal or invalid attempt state: {attempt}")

    results = [resolve_candidate(candidate, registry, resolver) for candidate in payload.get("candidates", [])]
    formal_count = sum(result["admissibility"] == "formal_evidence" for result in results)
    minimums = payload.get("required_minimums", {"formal_evidence": 1})
    formal_minimum = int(minimums.get("formal_evidence", 1))
    coverage_unmet = formal_count < formal_minimum
    registered_routes_exhausted = bool(route_attempts) and all(
        attempt.get("attempt_status") in TERMINAL_ATTEMPT_STATES for attempt in route_attempts
    )
    public_ocean_allowed = registered_routes_exhausted and coverage_unmet

    attestations = [
        attestation
        for result in results
        for attestation in result["resolution_attestations"]
    ]
    fallback_depth = max((result["fallback_depth"] for result in results), default=0)

    return {
        "reference_consumer_version": "0.1.0",
        "registry_release_id": release_id,
        "registry_data_version": manifest["schema_version"],
        "routing_policy_version": policy["policy_version"],
        "routing_policy_method": policy["method"],
        "routing_policy_sha256": sha256_bytes(policy_bytes),
        "source_profile_rule_version": profile_rules["schema_version"],
        "query_envelope": query_envelope,
        "route_attempts": route_attempts,
        "fallback_depth": fallback_depth,
        "results": results,
        "resolution_attestations": attestations,
        "coverage": {
            "formal_evidence_admissible": formal_count,
            "formal_evidence_minimum": formal_minimum,
            "coverage_unmet": coverage_unmet,
            "registered_routes_exhausted": registered_routes_exhausted,
            "public_ocean_allowed": public_ocean_allowed,
        },
        "limitations": policy["reference_implementation"]["limitations"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Structured query/candidate JSON")
    parser.add_argument("--output", type=Path, help="Write trace JSON to this path; stdout if omitted")
    parser.add_argument("--crossref-fixture", type=Path, help="Deterministic Crossref fixture for tests")
    args = parser.parse_args()

    payload = load_json(args.input)
    resolver: CrossrefResolver
    if args.crossref_fixture:
        resolver = FixtureCrossrefResolver(args.crossref_fixture)
    else:
        resolver = CrossrefResolver()
    trace = execute(payload, resolver)
    rendered = json.dumps(trace, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
