#!/usr/bin/env python3
from __future__ import annotations

import copy
import unittest

from reference_consumer.closed_search import (
    ClosedWorldViolation,
    classify_receipt,
    load_json,
    load_sources,
    plan_request,
    validate_trace,
)
from scripts.validate_chatbot_search import ROUTING_PATH, SCHEMA_PATH, validate

RELEASE = "a" * 40
OBSERVED = "2026-08-19T12:00:00Z"


class ChatbotSearchRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = load_json(ROUTING_PATH)
        cls.sources = load_sources()
        cls.schema = load_json(SCHEMA_PATH)

    def plan(self, source_id="openalex"):
        return plan_request(
            "machine learning & health",
            source_id,
            RELEASE,
            contract=self.contract,
            sources=self.sources,
        )

    def receipt(self, plan, **overrides):
        values = {
            "observed_url": plan["request_url"],
            "redirect_chain": [],
            "http_status": 200,
            "content_type": plan["accepted_content_types"][0] + "; charset=utf-8",
            "parse_succeeded": True,
            "result_count": 2,
            "observed_at": OBSERVED,
            "dedupe_key": "doi:10.1234/example",
        }
        values.update(overrides)
        return classify_receipt(plan, **values)

    def test_canonical_contract_validates_against_all_registry_shards(self):
        self.assertEqual(validate(self.contract, self.sources, self.schema), [])
        self.assertEqual(len(self.sources), 244)

    def test_unknown_source_is_closed_world_violation(self):
        with self.assertRaises(ClosedWorldViolation):
            self.plan("not-in-registry")

    def test_registered_source_without_adapter_is_explicit_gap(self):
        result = self.plan("tacl")
        self.assertEqual(result["status"], "NO_SEARCH_ADAPTER")
        self.assertEqual(result["target_source_id"], "tacl")

    def test_query_is_encoded_and_provider_equals_target(self):
        plan = self.plan()
        self.assertIn("machine%20learning%20%26%20health", plan["request_url"])
        self.assertEqual(plan["provider_source_id"], "openalex")
        self.assertEqual(plan["target_source_id"], "openalex")

    def test_unknown_adapter_source_is_rejected_by_validator(self):
        bad = copy.deepcopy(self.contract)
        bad["adapters"][0]["source_id"] = "not-in-registry"
        self.assertTrue(any("unknown registry source_id" in error for error in validate(bad, self.sources, self.schema)))

    def test_http_endpoint_is_rejected_by_validator(self):
        bad = copy.deepcopy(self.contract)
        bad["adapters"][0]["endpoint_template"] = bad["adapters"][0]["endpoint_template"].replace("https://", "http://")
        self.assertTrue(any("absolute HTTPS" in error for error in validate(bad, self.sources, self.schema)))

    def test_undeclared_host_is_rejected_by_validator(self):
        bad = copy.deepcopy(self.contract)
        bad["adapters"][0]["endpoint_template"] = "https://example.com/search?q={query}&limit={limit}"
        self.assertTrue(any("outside allowed_hosts" in error for error in validate(bad, self.sources, self.schema)))

    def test_wildcard_host_is_rejected_by_validator(self):
        bad = copy.deepcopy(self.contract)
        bad["adapters"][0]["allowed_hosts"] = ["*.ebi.ac.uk"]
        self.assertTrue(any("invalid allowed host" in error for error in validate(bad, self.sources, self.schema)))

    def test_ip_literal_and_explicit_port_are_rejected(self):
        bad = copy.deepcopy(self.contract)
        bad["adapters"][0]["allowed_hosts"] = ["127.0.0.1"]
        bad["adapters"][0]["endpoint_template"] = "https://127.0.0.1:8443/search?q={query}&limit={limit}"
        errors = validate(bad, self.sources, self.schema)
        self.assertTrue(any("IP-literal" in error for error in errors))
        self.assertTrue(any("explicit endpoint ports" in error for error in errors))

    def test_limit_outside_policy_budget_is_rejected(self):
        with self.assertRaises(ValueError):
            plan_request("topic", "openalex", RELEASE, limit=1000, contract=self.contract, sources=self.sources)

    def test_success_and_no_results_are_distinct(self):
        plan = self.plan()
        self.assertEqual(self.receipt(plan)["status"], "SUCCESS")
        self.assertEqual(self.receipt(plan, result_count=0, dedupe_key=None)["status"], "NO_RESULTS")

    def test_http_content_type_and_parse_failures_are_fetch_gaps(self):
        plan = self.plan()
        self.assertEqual(self.receipt(plan, http_status=429)["status"], "SOURCE_FETCH_GAP")
        self.assertEqual(self.receipt(plan, content_type="text/html")["status"], "SOURCE_FETCH_GAP")
        self.assertEqual(self.receipt(plan, parse_succeeded=False)["status"], "SOURCE_FETCH_GAP")

    def test_redirect_to_external_host_is_closed_world_violation(self):
        plan = self.plan()
        result = self.receipt(
            plan,
            observed_url="https://example.com/search",
            redirect_chain=["https://example.com/search"],
        )
        self.assertEqual(result["status"], "CLOSED_WORLD_VIOLATION")

    def test_trace_requires_release_and_host_receipt_fields(self):
        trace = self.receipt(self.plan())
        trace.pop("registry_release_id")
        with self.assertRaises(ClosedWorldViolation):
            validate_trace(trace, self.contract)

    def test_metadata_source_is_not_upgraded_to_fulltext(self):
        self.assertEqual(self.sources["openalex"]["oa_scope"], "metadata_only")
        plan = self.plan("openalex")
        self.assertNotIn("fulltext", plan)


if __name__ == "__main__":
    unittest.main()
