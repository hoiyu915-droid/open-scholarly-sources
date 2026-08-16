#!/usr/bin/env python3
"""Validate retrieval-routing invariants without third-party dependencies."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "data" / "retrieval-routing-policy.json"
SCHEMA_PATH = ROOT / "schemas" / "retrieval-routing-policy.schema.json"
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    policy = load(POLICY_PATH)
    schema = load(SCHEMA_PATH)

    required_top = {
        "schema_version",
        "policy_version",
        "method",
        "enforcement_scope",
        "repository_guarantee",
        "runtime_enforcement",
        "constraints",
        "modes",
        "requirements",
        "default_query_envelope",
        "deterministic_query_signals",
        "semantic_hints",
        "lanes",
        "route_order",
        "coverage_contract",
        "resolution",
        "admissibility_classes",
        "promotion",
        "trace_required_fields",
        "reference_implementation",
    }
    require(required_top <= set(policy), f"routing policy missing keys: {sorted(required_top - set(policy))}")
    require(policy["schema_version"] == "1.0.0", "unexpected routing policy schema_version")
    require(SEMVER_RE.fullmatch(policy["policy_version"]) is not None, "policy_version must be semver")
    require(policy["method"] == "registry_first_monotonic_fallback_v1", "unexpected routing method")
    require(policy["enforcement_scope"] == "consumer", "routing enforcement scope must remain consumer")
    require(policy["runtime_enforcement"] is False, "repository must not claim runtime enforcement")

    constraints = policy["constraints"]
    expected_constraints = {
        "uncertainty_may_widen_routes": True,
        "uncertainty_may_upgrade_evidence": False,
        "uncertainty_may_close_required_lane": False,
        "llm_may_set_verified": False,
        "public_ocean_may_bypass_resolution": False,
        "research_runtime_may_promote_registry": False,
    }
    require(constraints == expected_constraints, f"routing safety constraints drifted: {constraints}")

    require(policy["route_order"] == ["registry_direct", "registry_discovery", "public_ocean"], "route order must remain registry-first")
    coverage = policy["coverage_contract"]
    require(
        coverage["public_ocean_allowed_when"] == ["registered_routes_exhausted", "coverage_unmet"],
        "public ocean must require both registered-route exhaustion and unmet coverage",
    )
    require(
        set(coverage["terminal_attempt_states"])
        == {"success_with_candidates", "success_empty", "failed_after_policy_budget", "not_applicable"},
        "terminal attempt states drifted",
    )

    signals = policy["deterministic_query_signals"]
    require(signals["precision_target"] == "high", "deterministic signals must target high precision")
    require(signals["recall_target"] == "intentionally_low", "deterministic signals must declare intentionally low recall")
    require(signals["effect"] == "widen_only", "deterministic signals may only widen")

    hints = policy["semantic_hints"]
    require("widen" in hints["trusted_for"], "semantic hints must be allowed to widen")
    for forbidden in ("exclude_lane", "verify_evidence", "promote_registry_source"):
        require(forbidden in hints["forbidden_for"], f"semantic hints must forbid {forbidden}")

    resolution = policy["resolution"]
    require(resolution["public_ocean_default"] == "untrusted_until_resolved", "public-ocean candidates must start untrusted")
    require(resolution["new_source_peer_review_default"] == "unknown", "new-source peer review must default to unknown")
    require("crossref" not in resolution["accepted_resolvers"]["peer_review_scope"], "Crossref must not attest peer-review scope")
    require("crossref" in resolution["accepted_resolvers"]["document_identity"], "Crossref must remain a document-identity resolver")

    promotion = policy["promotion"]
    require(promotion["runtime_maximum_state"] == "registry_candidate", "research runtime may not promote beyond registry_candidate")
    require(promotion["canonical_admission_requires_separate_process"] is True, "canonical admission must be separate")
    require(promotion["observation_count_is_truth_evidence"] is False, "repeated observations may not count as truth evidence")

    lite = policy["modes"]["lite"]
    verified = policy["modes"]["verified"]
    require(set(lite["resolver_classes"]) <= set(verified["resolver_classes"]), "lite resolver set must be a subset of verified resolver set")
    require(lite["claim_boundary"] == "reduced_verification_never_increases_admissibility", "lite claim boundary drifted")

    requirements = set(policy["requirements"])
    require(set(policy["lanes"]) == requirements, "every requirement must have exactly one lane definition")
    for lane_name, lane in policy["lanes"].items():
        require(set(lane["default_companion_lanes"]) <= requirements, f"unknown companion lane in {lane_name}")
        require(bool(lane["admissibility_requires"]), f"lane {lane_name} must declare admissibility requirements")

    trace = set(policy["trace_required_fields"])
    for name in (
        "registry_release_id",
        "routing_policy_version",
        "routing_policy_sha256",
        "query_envelope",
        "route_attempts",
        "fallback_depth",
        "resolution_attestations",
    ):
        require(name in trace, f"trace contract missing {name}")

    require(schema.get("$id", "").endswith("/schemas/retrieval-routing-policy.schema.json"), "routing schema id mismatch")
    require(schema.get("additionalProperties") is False, "routing schema must reject unknown top-level properties")
    require(set(schema.get("required", [])) == required_top, "routing schema top-level required keys drifted")

    print(
        "Retrieval routing policy OK: "
        f"policy={policy['policy_version']} method={policy['method']} lanes={len(policy['lanes'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
