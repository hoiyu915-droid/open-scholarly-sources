#!/usr/bin/env python3
"""Validate the fail-closed, no-server chatbot search routing contract."""

from __future__ import annotations

import json
import ipaddress
import re
import sys
from datetime import date
from pathlib import Path
from string import Formatter
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MANIFEST_PATH = DATA / "registry-manifest.json"
ROUTING_PATH = DATA / "chatbot-search-routing.json"
SCHEMA_PATH = ROOT / "schemas" / "chatbot-search-routing.schema.json"

ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
HOST_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)
TOP_LEVEL_KEYS = {
    "schema_version", "protocol_version", "method", "updated", "default_mode",
    "runtime_enforcement", "network_boundary", "modes", "selection",
    "terminal_statuses", "gap_statuses", "trace_required_fields", "bootstrap",
    "brokered_discovery", "adapters",
}
ADAPTER_KEYS = {
    "adapter_id", "source_id", "status", "capability", "method",
    "endpoint_template", "query_encoding", "allowed_hosts", "redirect_policy",
    "response_format", "accepted_content_types", "parser", "authentication",
    "default_limit", "maximum_limit", "target_source_policy",
    "result_identity_fields", "oa_result_rule", "dedupe_key_order",
    "verification", "notes",
}
VERIFICATION_KEYS = {
    "live_status", "checked", "observed_http_status", "observed_content_type",
    "evidence_url",
}
BOOTSTRAP_KEYS = {
    "kind", "repository", "main_ref", "main_ref_api", "snapshot_ref",
    "release_index_path", "snapshot_path_template", "required_files",
    "file_identity", "freshness_rule", "pages_fallback_enabled",
}
BROKER_KEYS = {
    "broker_id", "status", "operation", "supported_tool_names",
    "domain_filter_required", "domain_match", "unrestricted_search_enabled",
    "snippets_are_evidence", "original_source_fetch_required_for_content_claims",
    "maximum_results_per_source", "direct_adapter_role", "runtime_failure_reuse",
    "eligible_source_count", "source_route_derivation",
}
SOURCE_ROUTE_KEYS = {
    "method", "required_source_status", "required_access_role",
    "required_canonical_url_scheme", "search_domain_rule", "search_query_rule",
    "candidate_host_rule", "origin_host_rule", "canonical_path_role",
    "shared_host_rule", "origin_identity_fields", "metadata_only_rule",
    "returned_link_rule", "identity_failure_status",
}


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"missing file: {path.relative_to(ROOT)}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")


def valid_date(value) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def unique_strings(value) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and item for item in value)
        and len(value) == len(set(value))
    )


def validate_hosts(label: str, hosts) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    if not unique_strings(hosts):
        return [], [f"{label}: hosts must be a non-empty unique array"]
    for host in hosts:
        if host != host.lower() or not HOST_RE.fullmatch(host):
            errors.append(f"{label}: invalid allowed host {host!r}")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if host == "localhost" or host.endswith(".localhost"):
                errors.append(f"{label}: local hosts are forbidden")
        else:
            errors.append(f"{label}: IP-literal hosts are forbidden")
    return hosts, errors


def valid_https_url(value) -> bool:
    parsed = urlparse(str(value or ""))
    return parsed.scheme == "https" and bool(parsed.hostname)


def source_records(manifest: dict) -> dict[str, dict]:
    records: dict[str, dict] = {}
    for filename in manifest.get("source_shards", []):
        shard = load(DATA / filename)
        for source in shard.get("sources", []):
            source_id = source.get("id")
            if source_id in records:
                raise SystemExit(f"duplicate registry source while validating chatbot routing: {source_id}")
            records[source_id] = source
    return records


def endpoint_bases(source: dict) -> list[str]:
    machine = source.get("machine_access", {})
    return [
        value.rstrip("/")
        for key in ("feed_url", "api_url", "oai_pmh_url", "bulk_metadata_url")
        if isinstance((value := machine.get(key)), str)
    ]


def matches_declared_endpoint(url: str, bases: list[str]) -> bool:
    candidate = urlparse(url)
    for value in bases:
        declared = urlparse(value)
        if candidate.scheme != declared.scheme or candidate.hostname != declared.hostname:
            continue
        try:
            if candidate.port != declared.port:
                continue
        except ValueError:
            continue
        boundary = declared.path or "/"
        if boundary.endswith("/"):
            if candidate.path.startswith(boundary):
                return True
        elif candidate.path == boundary or candidate.path.startswith(boundary + "/"):
            return True
    return False


def validate(policy: dict, sources: dict[str, dict], schema: dict) -> list[str]:
    errors: list[str] = []

    if not isinstance(policy, dict) or set(policy) != TOP_LEVEL_KEYS:
        errors.append(f"routing: top-level keys drifted: {sorted(set(policy or {}) ^ TOP_LEVEL_KEYS)}")
        return errors
    if policy.get("schema_version") != "2.0.0":
        errors.append("routing: unexpected schema_version")
    if policy.get("protocol_version") != "2.0.0":
        errors.append("routing: unexpected protocol_version")
    if policy.get("method") != "chatbot_registry_brokered_oa_search_v2":
        errors.append("routing: unexpected method")
    if not valid_date(policy.get("updated")):
        errors.append("routing: updated must be an ISO date")
    if policy.get("default_mode") != "registry_brokered":
        errors.append("routing: registry_brokered must be the default mode")
    if policy.get("runtime_enforcement") is not False:
        errors.append("routing: repository must not claim host runtime enforcement")

    boundary = policy.get("network_boundary")
    expected_boundary = {
        "custom_server_required": False,
        "skill_required": False,
        "radar_required": False,
        "public_ocean_evidence_enabled": False,
        "arbitrary_url_fetch_enabled": False,
        "domain_restricted_discovery_broker_enabled": True,
        "broker_result_content_is_evidence": False,
        "allowed_schemes": ["https"],
        "redirect_policy": "allowlisted_hosts_only",
    }
    if boundary != expected_boundary:
        errors.append("routing: network boundary must keep broker discovery non-evidentiary and fetches allowlisted")

    modes = policy.get("modes", {})
    if set(modes) != {"registry_brokered", "registry_closed", "direct_only"}:
        errors.append("routing: expected brokered, closed and direct-only modes")
    else:
        brokered_mode = modes["registry_brokered"]
        if brokered_mode.get("source_route_derived_from_registry") is not True:
            errors.append("routing: brokered source routes must be derived from the pinned registry")
        if brokered_mode.get("broker_is_evidence_source") is not False:
            errors.append("routing: discovery broker must never be an evidence source")
        if brokered_mode.get("origin_must_equal_target_source") is not True:
            errors.append("routing: brokered origin must remain the selected registered source")
        if modes["direct_only"].get("provider_must_equal_target") is not True:
            errors.append("routing: direct_only must require provider=target")

    selection = policy.get("selection", {})
    if selection.get("source_status_required") != "active":
        errors.append("routing: only active sources may be searched")
    if selection.get("direct_adapter_status_required") != "searchable":
        errors.append("routing: only searchable direct adapters may run")
    if selection.get("direct_no_adapter_status") != "NO_SEARCH_ADAPTER":
        errors.append("routing: missing adapters must fail as NO_SEARCH_ADAPTER")
    if not isinstance(selection.get("target_source_count"), int) or not isinstance(selection.get("maximum_source_count"), int):
        errors.append("routing: source-count bounds must be integers")
    elif selection["target_source_count"] > selection["maximum_source_count"]:
        errors.append("routing: target source count exceeds maximum")

    expected_terminal = [
        "SUCCESS", "NO_RESULTS", "NO_CANONICAL_SEARCH_ROUTE", "NO_SEARCH_ADAPTER",
        "SEARCH_BROKER_GAP", "SOURCE_IDENTITY_GAP", "ORIGINAL_FETCH_GAP",
        "FULLTEXT_NOT_AUTHORIZED", "SOURCE_FETCH_GAP", "CLOSED_WORLD_VIOLATION",
    ]
    if policy.get("terminal_statuses") != expected_terminal:
        errors.append("routing: terminal status contract drifted")
    expected_gaps = [
        "NO_CANONICAL_SEARCH_ROUTE", "NO_SEARCH_ADAPTER", "SEARCH_BROKER_GAP",
        "SOURCE_IDENTITY_GAP", "ORIGINAL_FETCH_GAP", "FULLTEXT_NOT_AUTHORIZED",
        "SOURCE_FETCH_GAP", "REGISTRY_COVERAGE_GAP", "CLOSED_WORLD_VIOLATION",
    ]
    if policy.get("gap_statuses") != expected_gaps:
        errors.append("routing: gap status contract drifted")
    required_trace = {
        "registry_release_id", "main_ref_commit_sha", "routing_sha256", "mode",
        "discovery_method", "broker_id", "broker_operation", "broker_query",
        "broker_domains", "broker_result_count", "source_route_id", "adapter_id",
        "provider_source_id", "target_source_id", "candidate_url",
        "candidate_identity_status", "request_url", "observed_url", "redirect_chain",
        "http_status", "content_type", "parser", "source_identity_verified",
        "original_record_observed", "evidence_class", "observed_at", "dedupe_key",
        "status",
    }
    if set(policy.get("trace_required_fields", [])) != required_trace:
        errors.append("routing: trace fields must preserve full release, route and host receipts")

    bootstrap = policy.get("bootstrap")
    expected_bootstrap = {
        "kind": "github_connector",
        "repository": "hoiyu915-droid/open-scholarly-sources",
        "main_ref": "main",
        "main_ref_api": "https://api.github.com/repos/hoiyu915-droid/open-scholarly-sources/branches/main",
        "snapshot_ref": "release-snapshots",
        "release_index_path": "releases/index.json",
        "snapshot_path_template": "releases/{release_id}/{path}",
        "required_files": [
            "release-manifest.json", "registry.json", "chatbot-search-routing.json",
            "chatbot-search-protocol.md", "chatbot-entry.txt",
            "schemas/chatbot-search-routing.schema.json",
        ],
        "file_identity": "manifest_sha256_and_git_blob_sha1",
        "freshness_rule": "release_index.current_release_id_equals_main_ref_commit_sha",
        "pages_fallback_enabled": False,
    }
    if not isinstance(bootstrap, dict) or set(bootstrap) != BOOTSTRAP_KEYS:
        errors.append("routing: invalid GitHub connector bootstrap keys")
    elif bootstrap != expected_bootstrap:
        errors.append("routing: GitHub connector bootstrap contract drifted")

    broker = policy.get("brokered_discovery")
    if not isinstance(broker, dict) or set(broker) != BROKER_KEYS:
        errors.append("routing: brokered discovery keys drifted")
    else:
        if broker.get("broker_id") != "host-web-search" or broker.get("operation") != "search_query":
            errors.append("routing: unexpected discovery broker identity")
        if broker.get("status") != "enabled" or broker.get("domain_filter_required") is not True:
            errors.append("routing: broker must require a domain-restricted search")
        if broker.get("domain_match") != "exact_declared_domain":
            errors.append("routing: broker domains must be exact")
        if broker.get("unrestricted_search_enabled") is not False:
            errors.append("routing: unrestricted broker search is forbidden")
        if broker.get("snippets_are_evidence") is not False:
            errors.append("routing: broker snippets cannot be evidence")
        if broker.get("original_source_fetch_required_for_content_claims") is not True:
            errors.append("routing: content claims must require an original-source fetch")
        if broker.get("direct_adapter_role") != "secondary_optional":
            errors.append("routing: direct adapters must remain optional secondary checks")
        if not unique_strings(broker.get("supported_tool_names")):
            errors.append("routing: broker tool names must be a non-empty unique array")
        maximum = broker.get("maximum_results_per_source")
        if not isinstance(maximum, int) or not 1 <= maximum <= 20:
            errors.append("routing: broker result limit must be between 1 and 20")
        expected_failure_reuse = {
            "same_task_retry_failed_host": False,
            "cross_task_reuse_without_reprobe": False,
            "observed_at_required": True,
        }
        if broker.get("runtime_failure_reuse") != expected_failure_reuse:
            errors.append("routing: runtime failure receipts must be task-scoped and timestamped")

        expected_route = {
            "method": "selected_registry_source_v1",
            "required_source_status": "active",
            "required_access_role": "discovery",
            "required_canonical_url_scheme": "https",
            "search_domain_rule": "exact_canonical_url_hostname",
            "search_query_rule": "topic_plus_exact_registered_source_name",
            "candidate_host_rule": "exact_canonical_url_hostname",
            "origin_host_rule": "exact_canonical_url_hostname",
            "canonical_path_role": "identity_hint_not_sufficient_proof",
            "shared_host_rule": "require_original_container_identity_before_acceptance",
            "origin_identity_fields": [
                "registered_source_name", "container_title", "issn_when_available",
                "repository_record_id_when_available", "doi_or_source_prefix_when_available",
            ],
            "metadata_only_rule": "may_support_registry_metadata_only_never_fulltext_claims",
            "returned_link_rule": "never_follow_cross_host_or_unregistered_target",
            "identity_failure_status": "SOURCE_IDENTITY_GAP",
        }
        route = broker.get("source_route_derivation")
        if not isinstance(route, dict) or set(route) != SOURCE_ROUTE_KEYS:
            errors.append("routing: registry-derived source route keys drifted")
        elif route != expected_route:
            errors.append("routing: registry-derived source route contract drifted")

        eligible_sources = []
        for source in sources.values():
            if source.get("status") != "active" or "discovery" not in source.get("access_roles", []):
                continue
            canonical = urlparse(str(source.get("canonical_url", "")))
            try:
                has_port = canonical.port is not None
            except ValueError:
                has_port = True
            if (
                canonical.scheme == "https" and canonical.hostname and not has_port
                and not canonical.username and not canonical.password and not canonical.fragment
            ):
                _, host_errors = validate_hosts(source.get("id", "source"), [canonical.hostname])
                if not host_errors:
                    eligible_sources.append(source)
        if broker.get("eligible_source_count") != len(eligible_sources):
            errors.append(
                f"routing: eligible source count drifted: {broker.get('eligible_source_count')} != {len(eligible_sources)}"
            )
        if not eligible_sources:
            errors.append("routing: brokered discovery resolved no active registry sources")

    adapter_ids: set[str] = set()
    source_ids: set[str] = set()
    for index, adapter in enumerate(policy.get("adapters", [])):
        label = adapter.get("adapter_id", f"adapter#{index}") if isinstance(adapter, dict) else f"adapter#{index}"
        if not isinstance(adapter, dict) or set(adapter) != ADAPTER_KEYS:
            errors.append(f"{label}: adapter keys drifted")
            continue
        adapter_id = adapter.get("adapter_id")
        source_id = adapter.get("source_id")
        if not isinstance(adapter_id, str) or not ID_RE.fullmatch(adapter_id):
            errors.append(f"{label}: invalid adapter_id")
        elif adapter_id in adapter_ids:
            errors.append(f"{label}: duplicate adapter_id")
        else:
            adapter_ids.add(adapter_id)
        if source_id in source_ids:
            errors.append(f"{label}: source has more than one active topic-search adapter")
        elif isinstance(source_id, str):
            source_ids.add(source_id)

        source = sources.get(source_id)
        if source is None:
            errors.append(f"{label}: unknown registry source_id {source_id!r}")
            continue
        if source.get("status") != "active":
            errors.append(f"{label}: source must be active")
        if adapter.get("status") != "searchable" or adapter.get("capability") != "topic_search":
            errors.append(f"{label}: active adapter must be searchable topic_search")
        if adapter.get("method") != "GET" or adapter.get("authentication") != "none":
            errors.append(f"{label}: no-server direct adapters permit only unauthenticated GET")
        if adapter.get("target_source_policy") != "same_as_provider":
            errors.append(f"{label}: direct adapters must fetch the selected registered source directly")
        if adapter.get("redirect_policy") != "same_host_only":
            errors.append(f"{label}: redirects must remain on the declared host")

        template = adapter.get("endpoint_template")
        if not isinstance(template, str):
            errors.append(f"{label}: endpoint_template must be a string")
            continue
        try:
            fields = [name for _, name, _, _ in Formatter().parse(template) if name]
        except ValueError:
            errors.append(f"{label}: invalid endpoint template")
            continue
        if sorted(fields) != ["limit", "query"]:
            errors.append(f"{label}: endpoint template must contain exactly query and limit placeholders")
        materialized = template.replace("{query}", "test").replace("{limit}", "1")
        parsed = urlparse(materialized)
        try:
            explicit_port = parsed.port is not None
        except ValueError:
            explicit_port = True
            errors.append(f"{label}: endpoint contains an invalid port")
        if parsed.scheme != "https" or not parsed.hostname:
            errors.append(f"{label}: endpoint must be an absolute HTTPS URL")
        if parsed.username or parsed.password or parsed.fragment:
            errors.append(f"{label}: endpoint must not contain userinfo or a fragment")

        hosts = adapter.get("allowed_hosts")
        hosts, host_errors = validate_hosts(label, hosts)
        errors.extend(host_errors)
        if parsed.hostname not in hosts:
            errors.append(f"{label}: endpoint host is outside allowed_hosts")
        if explicit_port:
            errors.append(f"{label}: explicit endpoint ports are forbidden")

        bases = endpoint_bases(source)
        if not matches_declared_endpoint(materialized, bases):
            errors.append(f"{label}: endpoint is not declared in source.machine_access")

        accepted = adapter.get("accepted_content_types")
        if not unique_strings(accepted) or any("/" not in value for value in (accepted or [])):
            errors.append(f"{label}: invalid accepted_content_types")
        if adapter.get("response_format") == "json" and "application/json" not in (accepted or []):
            errors.append(f"{label}: JSON route must accept application/json")
        if adapter.get("response_format") == "atom" and "application/atom+xml" not in (accepted or []):
            errors.append(f"{label}: Atom route must accept application/atom+xml")
        if not unique_strings(adapter.get("result_identity_fields")):
            errors.append(f"{label}: result_identity_fields must be non-empty and unique")
        if not unique_strings(adapter.get("dedupe_key_order")):
            errors.append(f"{label}: dedupe_key_order must be non-empty and unique")
        default_limit = adapter.get("default_limit")
        maximum_limit = adapter.get("maximum_limit")
        if not isinstance(default_limit, int) or not isinstance(maximum_limit, int) or not (1 <= default_limit <= maximum_limit <= 100):
            errors.append(f"{label}: invalid bounded result limits")

        verification = adapter.get("verification")
        if not isinstance(verification, dict) or set(verification) != VERIFICATION_KEYS:
            errors.append(f"{label}: invalid verification receipt")
        else:
            if verification.get("live_status") != "verified":
                errors.append(f"{label}: only live-verified endpoints may be searchable")
            if not valid_date(verification.get("checked")):
                errors.append(f"{label}: invalid verification date")
            status = verification.get("observed_http_status")
            if not isinstance(status, int) or not 200 <= status < 300:
                errors.append(f"{label}: searchable endpoint must have a successful live receipt")
            evidence = urlparse(str(verification.get("evidence_url", "")))
            if evidence.scheme != "https" or not evidence.netloc:
                errors.append(f"{label}: verification evidence must be HTTPS")

    if not adapter_ids:
        errors.append("routing: at least one live searchable adapter is required")
    if not source_ids <= set(sources):
        errors.append("routing: adapter source IDs must be a subset of the complete registry")

    if schema.get("$id") != "https://hoiyu915-droid.github.io/open-scholarly-sources/schemas/chatbot-search-routing.schema.json":
        errors.append("schema: $id mismatch")
    if schema.get("additionalProperties") is not False:
        errors.append("schema: top-level unknown properties must be rejected")
    if set(schema.get("required", [])) != TOP_LEVEL_KEYS:
        errors.append("schema: required top-level keys drifted")
    return errors


def main() -> int:
    manifest = load(MANIFEST_PATH)
    if manifest.get("chatbot_search_routing_file") != ROUTING_PATH.name:
        print("Chatbot search validation failed: registry manifest does not declare the routing file", file=sys.stderr)
        return 1
    sources = source_records(manifest)
    errors = validate(load(ROUTING_PATH), sources, load(SCHEMA_PATH))
    if errors:
        print(f"Chatbot search validation failed with {len(errors)} error(s):", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1
    routing = load(ROUTING_PATH)
    print(
        "Chatbot search routing OK: "
        f"protocol={routing['protocol_version']} adapters={len(routing['adapters'])} "
        f"brokered_sources={routing['brokered_discovery']['eligible_source_count']} "
        "mode=registry_brokered public_ocean_evidence=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
