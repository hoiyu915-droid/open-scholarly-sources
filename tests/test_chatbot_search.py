#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import copy
import inspect
import json
import unittest
from urllib.parse import urlparse

from scripts.validate_chatbot_search import ROUTING_PATH, SCHEMA_PATH, validate
from reference_consumer.closed_search import (
    ClosedWorldViolation,
    classify_broker_search,
    accept_brokered_candidate,
    classify_brokered_receipt,
    classify_receipt,
    load_json,
    load_sources,
    validate_connector_bootstrap,
    plan_brokered_search,
    plan_request,
    validate_trace,
)

RELEASE = "a" * 40
OBSERVED = "2026-08-19T12:00:00Z"


class ChatbotSearchRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = load_json(ROUTING_PATH)
        cls.sources = load_sources()
        cls.schema = load_json(SCHEMA_PATH)

    def broker_plan(self, source_id="openalex", registry_release_id=RELEASE, **kwargs):
        return plan_brokered_search(
            "machine learning & health",
            source_id,
            registry_release_id,
            contract=self.contract,
            sources=self.sources,
            **kwargs,
        )

    def direct_plan(self, source_id="openalex", registry_release_id=RELEASE, **kwargs):
        return plan_request(
            "machine learning & health",
            source_id,
            registry_release_id,
            contract=self.contract,
            sources=self.sources,
            **kwargs,
        )

    def direct_receipt(self, plan, **overrides):
        args = {
            "observed_url": plan["request_url"],
            "redirect_chain": [],
            "http_status": 200,
            "content_type": plan["accepted_content_types"][0] + "; charset=utf-8",
            "parse_succeeded": True,
            "result_count": 2,
            "observed_at": OBSERVED,
            "dedupe_key": "doi:10.1234/example",
        }
        args.update(overrides)
        signature = inspect.signature(classify_receipt)
        filtered = {name: value for name, value in args.items() if name in signature.parameters}
        return classify_receipt(plan, **filtered)

    def brokered_receipt(self, plan, **overrides):
        args = {
            "observed_url": plan.get("candidate_url", plan["request_url"]),
            "redirect_chain": [],
            "http_status": 200,
            "content_type": plan["accepted_content_types"][0] + "; charset=utf-8",
            "parse_succeeded": True,
            "source_identity_verified": True,
            "original_record_observed": True,
            "observed_at": OBSERVED,
            "dedupe_key": "doi:10.1234/example",
            "evidence_class": "fulltext",
        }
        args.update(overrides)
        signature = inspect.signature(classify_brokered_receipt)
        filtered = {name: value for name, value in args.items() if name in signature.parameters}
        return classify_brokered_receipt(plan, **filtered)

    def brokered_accept(self, plan, candidate_url):
        return accept_brokered_candidate(plan, candidate_url)

    def brokered_fetch_plan(self, source_id="openalex", candidate_url=None):
        plan = self.broker_plan(source_id)
        suffix = "articles/10.1000/example"
        source = self.sources[source_id]
        if candidate_url is None:
            candidate_url = source["canonical_url"].rstrip("/") + "/" + suffix
        return self.brokered_accept(plan, candidate_url)

    @staticmethod
    def canonical_host_for_source(source):
        return urlparse(source["canonical_url"]).hostname

    def first_inactive_source_id(self):
        for source_id, source in self.sources.items():
            if source.get("status") != "active":
                return source_id
        raise self.fail("no inactive source in fixture")

    @staticmethod
    def _sha256_digest(value) -> str:
        return hashlib.sha256(value).hexdigest()

    def _bootstrap_release_artifacts(self):
        required = self.contract["bootstrap"]["required_files"]
        release_artifacts = {
            "schema_version": "4.0.0",
            "release_id": RELEASE,
            "commit_sha": RELEASE,
            "repository_main_ref_api": self.contract["bootstrap"]["main_ref_api"],
            "chatbot_search_protocol_version": self.contract["protocol_version"],
            "chatbot_search_method": self.contract["method"],
            "chatbot_search_schema_version": self.contract["schema_version"],
            "chatbot_search_default_mode": self.contract["default_mode"],
            "chatbot_search_brokered_source_count": self.contract["brokered_discovery"]["eligible_source_count"],
            "chatbot_search_adapter_count": len(self.contract["adapters"]),
            "files": {},
        }
        for index, name in enumerate(required):
            if name == "release-manifest.json":
                continue
            release_artifacts["files"][name] = {
                "sha256": f"{index:064x}"[:64],
                "git_blob_sha1": f"{(index + 1):040x}"[:40],
                "bytes": 12,
            }
        manifest_sha256 = self._sha256_digest(
            json.dumps(release_artifacts, sort_keys=True, ensure_ascii=False).encode()
        )
        manifest_blob_sha1 = "a" * 40
        chatbot_identity = {
            key: release_artifacts[key]
            for key in (
                "chatbot_search_protocol_version",
                "chatbot_search_method",
                "chatbot_search_schema_version",
                "chatbot_search_default_mode",
                "chatbot_search_brokered_source_count",
                "chatbot_search_adapter_count",
            )
        }
        release_index = {
            "schema_version": "1.3.0",
            "current_release_id": RELEASE,
            "releases": [
                {
                    "release_id": RELEASE,
                    "commit_sha": RELEASE,
                    "manifest_sha256": manifest_sha256,
                    "manifest_git_blob_sha1": manifest_blob_sha1,
                    **chatbot_identity,
                }
            ],
        }
        return release_index, release_artifacts, manifest_sha256, manifest_blob_sha1

    def _connector_bootstrap_blob_map(self, release_manifest: dict, manifest_blob_sha1: str) -> dict[str, str]:
        blob_map = {
            name: metadata["git_blob_sha1"]
            for name, metadata in release_manifest["files"].items()
            if "git_blob_sha1" in metadata
        }
        blob_map["release-manifest.json"] = manifest_blob_sha1
        return blob_map

    def test_canonical_contract_validates_against_all_registry_shards(self):
        self.assertEqual(validate(self.contract, self.sources, self.schema), [])
        self.assertEqual(len(self.sources), 244)

    # Direct-mode regression tests kept for strict adapter behavior
    def test_unknown_source_is_closed_world_violation(self):
        with self.assertRaises(ClosedWorldViolation):
            self.direct_plan("not-in-registry")

    def test_registered_source_without_adapter_is_explicit_gap(self):
        result = self.direct_plan("tacl")
        self.assertEqual(result["status"], "NO_SEARCH_ADAPTER")
        self.assertEqual(result["target_source_id"], "tacl")
        validate_trace(result, self.contract)

    def test_no_adapter_trace_cannot_claim_external_network_receipts(self):
        for field, value in {
            "observed_url": "https://example.com/escape",
            "redirect_chain": ["https://example.com/escape"],
            "http_status": 200,
            "content_type": "text/html",
            "observed_at": "2026-08-19T12:00:00Z",
            "dedupe_key": "forged",
        }.items():
            with self.subTest(field=field):
                trace = self.direct_plan("tacl")
                trace[field] = value
                with self.assertRaises(ClosedWorldViolation):
                    validate_trace(trace, self.contract)

    def test_query_is_encoded_and_provider_equals_target(self):
        plan = self.direct_plan()
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

    def test_declared_endpoint_path_uses_a_real_boundary(self):
        bad = copy.deepcopy(self.contract)
        doaj = next(item for item in bad["adapters"] if item["source_id"] == "doaj")
        doaj["endpoint_template"] = "https://doaj.org/api-evil/search/articles/{query}?page=1&pageSize={limit}"
        self.assertTrue(any("not declared in source.machine_access" in error for error in validate(bad, self.sources, self.schema)))

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
            self.direct_plan("openalex", limit=1000)

    def test_success_and_no_results_are_distinct(self):
        plan = self.direct_plan()
        self.assertEqual(self.direct_receipt(plan)["status"], "SUCCESS")
        self.assertEqual(self.direct_receipt(plan, result_count=0, dedupe_key=None)["status"], "NO_RESULTS")

    def test_http_content_type_and_parse_failures_are_fetch_gaps(self):
        plan = self.direct_plan()
        self.assertEqual(self.direct_receipt(plan, http_status=429)["status"], "SOURCE_FETCH_GAP")
        self.assertEqual(self.direct_receipt(plan, content_type="text/html")["status"], "SOURCE_FETCH_GAP")
        self.assertEqual(self.direct_receipt(plan, parse_succeeded=False)["status"], "SOURCE_FETCH_GAP")

    def test_redirect_to_external_host_is_closed_world_violation(self):
        plan = self.direct_plan()
        result = self.direct_receipt(
            plan,
            observed_url="https://example.com/search",
            redirect_chain=["https://example.com/search"],
        )
        self.assertEqual(result["status"], "CLOSED_WORLD_VIOLATION")

    def test_trace_requires_release_and_host_receipt_fields(self):
        trace = self.direct_receipt(self.direct_plan())
        trace.pop("registry_release_id")
        with self.assertRaises(ClosedWorldViolation):
            validate_trace(trace, self.contract)

    def test_trace_revalidates_observed_urls_and_redirects(self):
        trace = self.direct_receipt(self.direct_plan())
        trace["observed_url"] = "https://example.com/search"
        trace["redirect_chain"] = ["https://example.com/search"]
        with self.assertRaises(ClosedWorldViolation):
            validate_trace(trace, self.contract)

    def test_trace_revalidates_mode_provider_target_parser_and_digests(self):
        mutations = {
            "mode": "other",
            "provider_source_id": "doaj",
            "target_source_id": "doaj",
            "parser": "forged_parser",
            "registry_release_id": "x" * 40,
            "routing_sha256": "0" * 64,
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                trace = self.direct_receipt(self.direct_plan())
                trace[field] = value
                with self.assertRaises(ClosedWorldViolation):
                    validate_trace(trace, self.contract)

    def test_trace_request_must_match_adapter_template(self):
        trace = self.direct_receipt(self.direct_plan())
        trace["request_url"] = "https://api.openalex.org/arbitrary"
        trace["observed_url"] = trace["request_url"]
        with self.assertRaises(ClosedWorldViolation):
            validate_trace(trace, self.contract)

    def test_plan_rejects_non_hex_release_identity(self):
        with self.assertRaises(ClosedWorldViolation):
            self.direct_plan("openalex", "x" * 40)

    def test_metadata_source_is_not_upgraded_to_fulltext(self):
        self.assertEqual(self.sources["openalex"]["oa_scope"], "metadata_only")
        plan = self.direct_plan("openalex")
        self.assertNotIn("fulltext", plan["accepted_content_types"])

    # Brokered-route tests for the new generic source-derived flow
    def test_brokered_plan_uses_dynamic_canonical_host_as_domain_restriction(self):
        plan = self.broker_plan("frontiers-psychology")
        self.assertEqual(plan["broker_domains"], [self.canonical_host_for_source(self.sources["frontiers-psychology"])])
        self.assertIn("frontiers", plan["broker_domains"][0])

        # verify another active source resolves to a different host
        non_frontiers = self.broker_plan("openalex")
        self.assertNotEqual(plan["broker_domains"], non_frontiers["broker_domains"])

    def test_frontiers_shared_host_requires_source_identity_before_acceptance(self):
        target_plan = self.broker_plan("frontiers-psychology")
        shared_host_url = self.sources["frontiers-social-psychology"]["canonical_url"] + "/articles/10.1000/example"
        accepted = self.brokered_accept(target_plan, shared_host_url)
        self.assertNotEqual(accepted["candidate_identity_status"], "VERIFIED")
        self.assertEqual(accepted["candidate_identity_status"], "HOST_ACCEPTED_IDENTITY_PENDING")
        fetched = self.brokered_receipt(
            accepted,
            source_identity_verified=False,
            original_record_observed=True,
            evidence_class="original_fulltext",
            broker_result_count=1,
        )
        self.assertEqual(fetched["status"], "SOURCE_IDENTITY_GAP")

    def test_external_or_restricted_broker_fetch_urls_are_rejected(self):
        fetch_plan = self.brokered_fetch_plan("frontiers-psychology")
        bad_urls = [
            "https://www.frontiersin.org:443/escape",
            "https://user:pass@www.frontiersin.org/articles/10.1000/example",
            "https://www.frontiersin.org/articles/10.1000/example#section",
            "https://www.frontiersin.org/..%2f..%2fetc/passwd",
        ]
        for bad_url in bad_urls:
            with self.subTest(bad_url=bad_url):
                trace = self.brokered_receipt(
                    fetch_plan,
                    observed_url=bad_url,
                    redirect_chain=[bad_url],
                )
                self.assertEqual(trace["status"], "CLOSED_WORLD_VIOLATION")

    def test_external_observed_url_or_redirect_causes_closed_world_violation(self):
        fetch_plan = self.brokered_fetch_plan("frontiers-psychology")
        for bad_url in ("https://example.com/escape", "https://frontiersin.org.evil/path"):
            with self.subTest(bad_url=bad_url):
                trace = self.brokered_receipt(
                    fetch_plan,
                    observed_url=bad_url,
                    redirect_chain=[bad_url],
                )
                self.assertEqual(trace["status"], "CLOSED_WORLD_VIOLATION")

    def test_broker_receipt_snippet_is_original_fetch_gap(self):
        plan = self.brokered_fetch_plan("frontiers-psychology")
        trace = self.brokered_receipt(
            plan,
            source_identity_verified=True,
            original_record_observed=True,
            evidence_class="discovery_snippet",
        )
        self.assertEqual(trace["status"], "ORIGINAL_FETCH_GAP")

    def test_original_fetch_failures_map_to_original_fetch_gap(self):
        plan = self.brokered_fetch_plan("frontiers-psychology")
        self.assertEqual(self.brokered_receipt(plan, http_status=403)["status"], "ORIGINAL_FETCH_GAP")
        self.assertEqual(
            self.brokered_receipt(plan, evidence_class="discovery_snippet")["status"],
            "ORIGINAL_FETCH_GAP",
        )
        self.assertEqual(
            self.brokered_receipt(plan, parse_succeeded=False, evidence_class="original_fulltext")["status"],
            "ORIGINAL_FETCH_GAP",
        )

    def test_metadata_only_source_cannot_claim_fulltext(self):
        source = self.sources["openalex"]
        self.assertEqual(source["oa_scope"], "metadata_only")
        plan = self.brokered_fetch_plan("openalex")
        self.assertEqual(
            self.brokered_receipt(
                plan,
                evidence_class="original_fulltext",
                source_identity_verified=True,
                original_record_observed=True,
            )["status"],
            "FULLTEXT_NOT_AUTHORIZED",
        )

    def test_inactive_or_unknown_source_is_fail_closed(self):
        with self.assertRaises(ClosedWorldViolation):
            self.broker_plan("not-a-source")
        with self.assertRaises(ClosedWorldViolation):
            self.broker_plan(self.first_inactive_source_id())

    def test_no_results_is_only_emitted_for_zero_result_broker_receipt(self):
        plan = self.broker_plan("frontiers-psychology")
        trace = classify_broker_search(plan, candidate_urls=[], observed_at=OBSERVED)
        self.assertEqual(trace["status"], "NO_RESULTS")
        self.assertEqual(trace["broker_result_count"], 0)
        self.assertIsNone(trace["candidate_url"])
        self.assertIsNone(trace["request_url"])

        gap = classify_broker_search(plan, candidate_urls=None, observed_at=OBSERVED)
        self.assertEqual(gap["status"], "SEARCH_BROKER_GAP")
        self.assertIsNone(gap["broker_result_count"])
        with self.assertRaises(ValueError):
            classify_broker_search(plan, candidate_urls=["https://www.frontiersin.org/articles/10.1000/example"], observed_at=OBSERVED)

    def test_strict_adapter_is_secondary_optional(self):
        self.assertEqual(self.contract["brokered_discovery"]["direct_adapter_role"], "secondary_optional")

    def test_connector_bootstrap_validates_valid_manifest_bundle(self):
        release_index, release_manifest, manifest_sha256, manifest_blob_sha1 = self._bootstrap_release_artifacts()
        validate_connector_bootstrap(
            main_ref_commit_sha=RELEASE,
            release_index=release_index,
            release_manifest=release_manifest,
            fetched_git_blob_sha1=self._connector_bootstrap_blob_map(release_manifest, manifest_blob_sha1),
            fetched_release_manifest_sha256=manifest_sha256,
            contract=self.contract,
        )

    def test_connector_bootstrap_rejects_main_index_release_mismatch(self):
        release_index, release_manifest, _, manifest_blob_sha1 = self._bootstrap_release_artifacts()
        release_index["current_release_id"] = "b" * 40
        with self.assertRaises(ClosedWorldViolation):
            validate_connector_bootstrap(
                main_ref_commit_sha=RELEASE,
                release_index=release_index,
                release_manifest=release_manifest,
                fetched_git_blob_sha1=self._connector_bootstrap_blob_map(release_manifest, manifest_blob_sha1),
                contract=self.contract,
            )

    def test_connector_bootstrap_rejects_release_manifest_sha_mismatch(self):
        release_index, release_manifest, manifest_sha256, manifest_blob_sha1 = self._bootstrap_release_artifacts()
        release_index["releases"][0]["manifest_sha256"] = "b" * 64
        with self.assertRaises(ClosedWorldViolation):
            validate_connector_bootstrap(
                main_ref_commit_sha=RELEASE,
                release_index=release_index,
                release_manifest=release_manifest,
                fetched_git_blob_sha1=self._connector_bootstrap_blob_map(release_manifest, manifest_blob_sha1),
                fetched_release_manifest_sha256=manifest_sha256,
                contract=self.contract,
            )

    def test_connector_bootstrap_rejects_manifest_file_blob_sha_mismatch(self):
        release_index, release_manifest, _, manifest_blob_sha1 = self._bootstrap_release_artifacts()
        fetched_blob_sha1 = self._connector_bootstrap_blob_map(release_manifest, manifest_blob_sha1)
        # keep manifest metadata consistent; inject mismatch at the connector return layer.
        fetched_blob_sha1["release-manifest.json"] = "b" * 40
        with self.assertRaises(ClosedWorldViolation):
            validate_connector_bootstrap(
                main_ref_commit_sha=RELEASE,
                release_index=release_index,
                release_manifest=release_manifest,
                fetched_git_blob_sha1=fetched_blob_sha1,
                contract=self.contract,
            )

    def test_connector_bootstrap_rejects_required_file_blob_sha_mismatch(self):
        release_index, release_manifest, _, manifest_blob_sha1 = self._bootstrap_release_artifacts()
        fetched_blob_sha1 = self._connector_bootstrap_blob_map(release_manifest, manifest_blob_sha1)
        fetched_blob_sha1["registry.json"] = "b" * 40
        with self.assertRaises(ClosedWorldViolation):
            validate_connector_bootstrap(
                main_ref_commit_sha=RELEASE,
                release_index=release_index,
                release_manifest=release_manifest,
                fetched_git_blob_sha1=fetched_blob_sha1,
                contract=self.contract,
            )


if __name__ == "__main__":
    unittest.main()
