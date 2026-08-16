#!/usr/bin/env python3
"""Explicit opt-in verification reference consumer.

Open Scholarly Sources defaults to source navigation only. This module is the
reference entry point for the optional verification route. It refuses to run
unless the caller supplies `verification.enabled=true`.

The implementation currently demonstrates the lite formal-evidence candidate
gate with Crossref document identity plus pinned-registry source-scope facts.
It is deliberately not the default literature-discovery path.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from reference_consumer.route import (
    CrossrefResolver,
    FixtureCrossrefResolver,
    POLICY_PATH,
    PROFILE_RULES_PATH,
    RELEASE_ID_RE,
    TERMINAL_ATTEMPT_STATES,
    load_json,
    load_registry,
    resolve_candidate,
    sha256_bytes,
)


def execute(payload: dict, resolver: CrossrefResolver) -> dict:
    policy = load_json(POLICY_PATH)
    policy_bytes = POLICY_PATH.read_bytes()
    profile_rules = load_json(PROFILE_RULES_PATH)
    manifest, registry = load_registry()

    verification = payload.get("verification")
    if not isinstance(verification, dict) or verification.get("enabled") is not True:
        raise SystemExit(
            "verification is opt-in; set verification.enabled=true only after explicit user request"
        )
    profile = verification.get("profile")
    if profile not in policy["verification_profiles"]:
        raise SystemExit("verification.profile is not allowed by routing policy")
    if profile != "lite":
        raise SystemExit("reference consumer v0.2 currently implements the lite verification profile only")

    release_id = payload.get("registry_release_id")
    if not isinstance(release_id, str) or RELEASE_ID_RE.fullmatch(release_id) is None:
        raise SystemExit("registry_release_id must be a full 40-character lowercase hex commit SHA")

    query_envelope = payload.get("query_envelope", {})
    requirements = query_envelope.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        raise SystemExit("query_envelope.requirements must be a non-empty list")
    unknown_requirements = sorted(set(requirements) - set(policy["verification_requirements"]))
    if unknown_requirements:
        raise SystemExit(f"unknown verification requirements: {unknown_requirements}")
    if "formal_evidence" not in requirements:
        raise SystemExit("reference consumer v0.2 requires formal_evidence")

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
    public_ocean_allowed = (
        verification.get("enabled") is True
        and registered_routes_exhausted
        and coverage_unmet
    )

    attestations = [
        attestation
        for result in results
        for attestation in result["resolution_attestations"]
    ]
    fallback_depth = max((result["fallback_depth"] for result in results), default=0)

    return {
        "reference_consumer_version": "0.2.0",
        "registry_release_id": release_id,
        "registry_data_version": manifest["schema_version"],
        "routing_policy_version": policy["policy_version"],
        "routing_policy_method": policy["method"],
        "routing_policy_sha256": sha256_bytes(policy_bytes),
        "source_profile_rule_version": profile_rules["schema_version"],
        "verification": verification,
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
    parser.add_argument("--input", type=Path, required=True, help="Explicit verification request/candidate JSON")
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
