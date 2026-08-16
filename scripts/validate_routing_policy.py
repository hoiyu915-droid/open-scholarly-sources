#!/usr/bin/env python3
"""Validate retrieval-routing invariants without third-party dependencies."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "data" / "retrieval-routing-policy.json"
SCHEMA_PATH = ROOT / "schemas" / "retrieval-routing-policy.schema.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    policy = load(POLICY_PATH)
    schema = load(SCHEMA_PATH)

    required_top = {
        "schema_version", "policy_version", "method", "enforcement_scope",
        "repository_guarantee", "runtime_enforcement", "default_behavior",
        "navigation", "verification_activation", "verification_profiles",
        "verification_constraints", "verification_requirements",
        "verification_lanes", "verification_route_order", "coverage_contract",
        "resolution", "admissibility_classes", "promotion",
        "verification_trace_required_fields", "reference_implementation",
    }
    require(required_top == set(policy), f"routing policy top-level keys drifted: {sorted(set(policy) ^ required_top)}")
    require(policy["schema_version"] == "2.0.0", "unexpected routing policy schema_version")
    require(policy["policy_version"] == "2.0.0", "unexpected routing policy_version")
    require(policy["method"] == "registry_source_navigation_opt_in_verification_v2", "unexpected routing method")
    require(policy["enforcement_scope"] == "consumer", "routing enforcement scope must remain consumer")
    require(policy["runtime_enforcement"] is False, "repository must not claim runtime enforcement")

    default = policy["default_behavior"]
    require(default["mode"] == "source_navigation", "default mode must be source_navigation")
    require(default["verification_enabled"] is False, "verification must be disabled by default")
    require(default["public_ocean_enabled"] is False, "public ocean must be disabled by default")
    forbidden = set(default["forbidden_default_actions"])
    for action in (
        "resolve_documents", "query_crossref", "query_doaj", "query_unpaywall",
        "judge_document_admissibility", "emit_resolution_attestations",
        "open_public_ocean",
    ):
        require(action in forbidden, f"default source navigation must forbid {action}")
    require(default["suggested_source_count"]["target"] <= default["suggested_source_count"]["maximum"], "source suggestion target exceeds maximum")

    navigation = policy["navigation"]
    require(navigation["source_of_truth"] == "pinned_open_scholarly_sources_registry_release", "navigation must use pinned registry release")
    require(navigation["llm_semantic_matching_allowed"] is True, "LLM may semantically rank registered sources")
    require(navigation["result_contract"] == "point_the_user_to_the_best_registered_places_to_dig_for_literature", "navigation result contract drifted")

    activation = policy["verification_activation"]
    require(activation["enabled_by_default"] is False, "verification activation must default off")
    require(activation["requires"] == "explicit_user_opt_in", "verification must require explicit user opt-in")
    require(activation["llm_may_self_activate"] is False, "LLM must not self-activate verification")

    constraints = policy["verification_constraints"]
    expected_constraints = {
        "uncertainty_may_widen_routes": True,
        "uncertainty_may_upgrade_evidence": False,
        "uncertainty_may_close_required_lane": False,
        "llm_may_set_verified": False,
        "public_ocean_may_bypass_resolution": False,
        "research_runtime_may_promote_registry": False,
    }
    require(constraints == expected_constraints, f"verification safety constraints drifted: {constraints}")

    lite = policy["verification_profiles"]["lite"]
    verified = policy["verification_profiles"]["verified"]
    require(set(lite["resolver_classes"]) <= set(verified["resolver_classes"]), "lite resolver set must be a subset of verified resolver set")
    require(lite["claim_boundary"] == "reduced_verification_never_increases_admissibility", "lite claim boundary drifted")

    requirements = set(policy["verification_requirements"])
    require(set(policy["verification_lanes"]) == requirements, "every verification requirement must have exactly one lane definition")
    for lane_name, lane in policy["verification_lanes"].items():
        require(set(lane["default_companion_lanes"]) <= requirements, f"unknown companion lane in {lane_name}")
        require(bool(lane["admissibility_requires"]), f"lane {lane_name} must declare admissibility requirements")

    require(policy["verification_route_order"] == ["registry_direct", "registry_discovery", "public_ocean"], "verification route order must remain registry-first")
    coverage = policy["coverage_contract"]
    require(coverage["planned_route_accounting_required"] is True, "verification fallback must account for every planned registered route")
    require(
        coverage["registered_routes_exhausted_when"] == "every_planned_registered_route_has_one_terminal_attempt",
        "registered route exhaustion must be computed from the declared route plan",
    )
    require(
        coverage["public_ocean_allowed_when"] == ["verification_enabled", "registered_routes_exhausted", "coverage_unmet"],
        "public ocean must require explicit verification plus exhaustion and unmet coverage",
    )
    require(
        set(coverage["terminal_attempt_states"])
        == {"success_with_candidates", "success_empty", "failed_after_policy_budget", "not_applicable"},
        "terminal attempt states drifted",
    )

    resolution = policy["resolution"]
    require(resolution["public_ocean_default"] == "untrusted_until_resolved", "public-ocean candidates must start untrusted")
    require(resolution["new_source_peer_review_default"] == "unknown", "new-source peer review must default to unknown")
    require("crossref" not in resolution["accepted_resolvers"]["peer_review_scope"], "Crossref must not attest peer-review scope")
    require("crossref" in resolution["accepted_resolvers"]["document_identity"], "Crossref must remain a document-identity resolver")

    promotion = policy["promotion"]
    require(promotion["runtime_maximum_state"] == "registry_candidate", "research runtime may not promote beyond registry_candidate")
    require(promotion["canonical_admission_requires_separate_process"] is True, "canonical admission must be separate")
    require(promotion["observation_count_is_truth_evidence"] is False, "repeated observations may not count as truth evidence")

    trace = set(policy["verification_trace_required_fields"])
    for name in (
        "registry_release_id", "routing_policy_version", "routing_policy_sha256",
        "verification", "query_envelope", "planned_registered_routes",
        "route_attempts", "fallback_depth", "resolution_attestations",
    ):
        require(name in trace, f"verification trace contract missing {name}")

    reference = policy["reference_implementation"]
    require(reference["path"] == "reference_consumer/verify.py", "verification reference entry point drifted")
    require(reference["activation_required"] is True, "reference consumer must require explicit verification activation")
    require(reference["scope"] == "explicit_verification_formal_evidence_candidate_gate_v0_2", "reference consumer scope drifted")

    require(schema.get("$id", "").endswith("/schemas/retrieval-routing-policy.schema.json"), "routing schema id mismatch")
    require(schema.get("additionalProperties") is False, "routing schema must reject unknown top-level properties")
    require(set(schema.get("required", [])) == required_top, "routing schema top-level required keys drifted")

    print(
        "Retrieval routing policy OK: "
        f"policy={policy['policy_version']} default={default['mode']} verification=opt-in"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
