#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

from reference_consumer.route import FixtureCrossrefResolver
from reference_consumer.verify import execute

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "reference_consumer" / "crossref-fixture.json"
RELEASE = "0" * 40


def payload(candidates, attempt_status="success_with_candidates", minimum=1):
    route_id = "formal:tacl"
    return {
        "registry_release_id": RELEASE,
        "verification": {
            "enabled": True,
            "profile": "lite",
            "requested_by": "user"
        },
        "query_envelope": {
            "requirements": ["formal_evidence"],
            "freshness": "unspecified"
        },
        "planned_registered_routes": [
            {
                "route_id": route_id,
                "lane": "formal_evidence",
                "source_id": "tacl"
            }
        ],
        "route_attempts": [
            {
                "route_id": route_id,
                "lane": "formal_evidence",
                "source_id": "tacl",
                "attempt_status": attempt_status,
                "query_digest": "fixture"
            }
        ],
        "required_minimums": {"formal_evidence": minimum},
        "candidates": candidates
    }


class ReferenceConsumerTests(unittest.TestCase):
    def setUp(self):
        self.resolver = FixtureCrossrefResolver(FIXTURE)

    def test_verification_must_be_explicitly_enabled(self):
        request = payload([])
        request.pop("verification")
        with self.assertRaises(SystemExit):
            execute(request, self.resolver)

    def test_disabled_verification_is_rejected(self):
        request = payload([])
        request["verification"]["enabled"] = False
        with self.assertRaises(SystemExit):
            execute(request, self.resolver)

    def test_llm_may_not_self_activate_verification(self):
        request = payload([])
        request["verification"]["requested_by"] = "llm"
        with self.assertRaises(SystemExit):
            execute(request, self.resolver)

    def test_known_verified_registry_journal_is_formal_admissible(self):
        trace = execute(
            payload([
                {
                    "doi": "10.5555/oss-tacl-known",
                    "source_hint": "tacl",
                    "route": "registry_direct"
                }
            ]),
            self.resolver,
        )
        self.assertEqual(trace["results"][0]["admissibility"], "formal_evidence")
        self.assertEqual(trace["results"][0]["source_id"], "tacl")
        self.assertFalse(trace["coverage"]["coverage_unmet"])
        self.assertFalse(trace["coverage"]["public_ocean_allowed"])
        self.assertTrue(trace["verification"]["enabled"])
        self.assertEqual(trace["verification"]["requested_by"], "user")
        self.assertEqual(trace["reference_consumer_version"], "0.2.0")
        self.assertEqual(len(trace["routing_policy_sha256"]), 64)

    def test_unknown_journal_with_valid_doi_remains_discovery_only(self):
        trace = execute(
            payload([
                {
                    "doi": "10.5555/oss-unknown-journal",
                    "route": "public_ocean"
                }
            ]),
            self.resolver,
        )
        self.assertEqual(trace["results"][0]["admissibility"], "discovery_only")
        self.assertEqual(trace["results"][0]["reason"], "no_registry_container_match")
        self.assertTrue(trace["coverage"]["coverage_unmet"])
        self.assertTrue(trace["coverage"]["public_ocean_allowed"])
        self.assertEqual(trace["fallback_depth"], 2)

    def test_unresolved_doi_does_not_enter_evidence_lane(self):
        trace = execute(
            payload([
                {
                    "doi": "10.5555/oss-missing",
                    "route": "public_ocean"
                }
            ]),
            self.resolver,
        )
        self.assertEqual(trace["results"][0]["admissibility"], "unresolved")
        self.assertTrue(trace["coverage"]["coverage_unmet"])
        self.assertTrue(trace["coverage"]["public_ocean_allowed"])

    def test_success_empty_registered_route_opens_public_ocean_only_inside_verification(self):
        trace = execute(payload([], attempt_status="success_empty"), self.resolver)
        self.assertEqual(trace["coverage"]["formal_evidence_admissible"], 0)
        self.assertTrue(trace["coverage"]["registered_routes_exhausted"])
        self.assertTrue(trace["coverage"]["coverage_unmet"])
        self.assertTrue(trace["coverage"]["public_ocean_allowed"])

    def test_incomplete_planned_route_accounting_does_not_open_public_ocean(self):
        request = payload([], attempt_status="success_empty")
        request["planned_registered_routes"].append(
            {
                "route_id": "formal:second-source",
                "lane": "formal_evidence",
                "source_id": "second-source"
            }
        )
        trace = execute(request, self.resolver)
        self.assertFalse(trace["coverage"]["registered_routes_exhausted"])
        self.assertTrue(trace["coverage"]["coverage_unmet"])
        self.assertFalse(trace["coverage"]["public_ocean_allowed"])

    def test_unplanned_attempt_is_rejected(self):
        bad = payload([])
        bad["route_attempts"][0]["route_id"] = "formal:not-planned"
        with self.assertRaises(SystemExit):
            execute(bad, self.resolver)

    def test_nonterminal_attempt_is_rejected(self):
        bad = payload([])
        bad["route_attempts"][0]["attempt_status"] = "running"
        with self.assertRaises(SystemExit):
            execute(bad, self.resolver)


if __name__ == "__main__":
    unittest.main()
