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
TOP_LEVEL_KEYS = {
    "schema_version", "protocol_version", "method", "updated", "default_mode",
    "runtime_enforcement", "network_boundary", "modes", "selection",
    "terminal_statuses", "gap_statuses", "trace_required_fields", "adapters",
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


def validate(policy: dict, sources: dict[str, dict], schema: dict) -> list[str]:
    errors: list[str] = []

    if not isinstance(policy, dict) or set(policy) != TOP_LEVEL_KEYS:
        errors.append(f"routing: top-level keys drifted: {sorted(set(policy or {}) ^ TOP_LEVEL_KEYS)}")
        return errors
    if policy.get("schema_version") != "1.0.0":
        errors.append("routing: unexpected schema_version")
    if policy.get("protocol_version") != "1.0.0":
        errors.append("routing: unexpected protocol_version")
    if policy.get("method") != "chatbot_closed_registry_oa_search_v1":
        errors.append("routing: unexpected method")
    if not valid_date(policy.get("updated")):
        errors.append("routing: updated must be an ISO date")
    if policy.get("default_mode") != "registry_closed":
        errors.append("routing: registry_closed must remain the default mode")
    if policy.get("runtime_enforcement") is not False:
        errors.append("routing: repository must not claim host runtime enforcement")

    boundary = policy.get("network_boundary")
    expected_boundary = {
        "custom_server_required": False,
        "skill_required": False,
        "public_ocean_enabled": False,
        "arbitrary_url_fetch_enabled": False,
        "allowed_schemes": ["https"],
        "redirect_policy": "same_host_only",
    }
    if boundary != expected_boundary:
        errors.append("routing: network boundary must remain HTTPS-only, server-free and closed-world")

    modes = policy.get("modes", {})
    if set(modes) != {"registry_closed", "direct_only"}:
        errors.append("routing: expected exactly registry_closed and direct_only modes")
    elif modes["direct_only"].get("provider_must_equal_target") is not True:
        errors.append("routing: direct_only must require provider=target")

    selection = policy.get("selection", {})
    if selection.get("source_status_required") != "active":
        errors.append("routing: only active sources may be searched")
    if selection.get("adapter_status_required") != "searchable":
        errors.append("routing: only searchable adapters may run")
    if selection.get("no_adapter_status") != "NO_SEARCH_ADAPTER":
        errors.append("routing: missing adapters must fail as NO_SEARCH_ADAPTER")
    if not isinstance(selection.get("target_source_count"), int) or not isinstance(selection.get("maximum_source_count"), int):
        errors.append("routing: source-count bounds must be integers")
    elif selection["target_source_count"] > selection["maximum_source_count"]:
        errors.append("routing: target source count exceeds maximum")

    expected_terminal = [
        "SUCCESS", "NO_RESULTS", "NO_SEARCH_ADAPTER", "SOURCE_FETCH_GAP",
        "CLOSED_WORLD_VIOLATION",
    ]
    if policy.get("terminal_statuses") != expected_terminal:
        errors.append("routing: terminal status contract drifted")
    expected_gaps = [
        "NO_SEARCH_ADAPTER", "SOURCE_FETCH_GAP", "REGISTRY_COVERAGE_GAP",
        "CLOSED_WORLD_VIOLATION",
    ]
    if policy.get("gap_statuses") != expected_gaps:
        errors.append("routing: gap status contract drifted")
    required_trace = {
        "registry_release_id", "routing_sha256", "mode", "adapter_id",
        "provider_source_id", "target_source_id", "request_url", "observed_url",
        "redirect_chain", "http_status", "content_type", "parser", "observed_at",
        "dedupe_key", "status",
    }
    if set(policy.get("trace_required_fields", [])) != required_trace:
        errors.append("routing: trace fields must preserve full release, route and host receipts")

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
            errors.append(f"{label}: no-server v1 permits only unauthenticated GET")
        if adapter.get("target_source_policy") != "same_as_provider":
            errors.append(f"{label}: v1 adapters must fetch the selected registered source directly")
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
        if not unique_strings(hosts):
            errors.append(f"{label}: allowed_hosts must be a non-empty unique array")
            hosts = []
        for host in hosts:
            if host != host.lower() or "*" in host or ":" in host or "/" in host:
                errors.append(f"{label}: invalid allowed host {host!r}")
            try:
                ipaddress.ip_address(host)
            except ValueError:
                if host == "localhost" or host.endswith(".localhost"):
                    errors.append(f"{label}: local hosts are forbidden")
            else:
                errors.append(f"{label}: IP-literal hosts are forbidden")
        if parsed.hostname not in hosts:
            errors.append(f"{label}: endpoint host is outside allowed_hosts")
        if explicit_port:
            errors.append(f"{label}: explicit endpoint ports are forbidden")

        bases = endpoint_bases(source)
        if not any(materialized.startswith(base) for base in bases):
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
        "mode=registry_closed public_ocean=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
