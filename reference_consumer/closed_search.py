#!/usr/bin/env python3
"""Pure contract helpers for a closed-registry chatbot search implementation.

This module does not perform network requests. It demonstrates deterministic
planning and fail-closed receipt classification for chatbot hosts.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import quote, urlparse

ROOT = Path(__file__).resolve().parents[1]
ROUTING_PATH = ROOT / "data" / "chatbot-search-routing.json"
MANIFEST_PATH = ROOT / "data" / "registry-manifest.json"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ClosedWorldViolation(ValueError):
    """Raised before a request when a source, route or URL escapes the registry."""


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_sources() -> dict[str, dict]:
    manifest = load_json(MANIFEST_PATH)
    sources: dict[str, dict] = {}
    for filename in manifest["source_shards"]:
        for source in load_json(ROOT / "data" / filename)["sources"]:
            if source["id"] in sources:
                raise ClosedWorldViolation(f"duplicate registry source: {source['id']}")
            sources[source["id"]] = source
    return sources


def routing_sha256() -> str:
    return hashlib.sha256(ROUTING_PATH.read_bytes()).hexdigest()


def _adapter_map(contract: dict) -> dict[str, dict]:
    return {adapter["source_id"]: adapter for adapter in contract["adapters"]}


def _assert_allowed_url(url: str, adapter: dict) -> None:
    parsed = urlparse(url)
    try:
        explicit_port = parsed.port is not None
    except ValueError as exc:
        raise ClosedWorldViolation(f"URL contains an invalid port: {url}") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname not in adapter["allowed_hosts"]
        or parsed.username
        or parsed.password
        or parsed.fragment
        or explicit_port
    ):
        raise ClosedWorldViolation(f"URL outside adapter allowlist: {url}")


def _assert_request_matches_template(url: str, adapter: dict) -> None:
    pattern = re.escape(adapter["endpoint_template"])
    pattern = pattern.replace(re.escape("{query}"), r"(?P<query>[^/?#&]+)")
    pattern = pattern.replace(re.escape("{limit}"), r"(?P<limit>[0-9]+)")
    match = re.fullmatch(pattern, url)
    if match is None or not match.group("query"):
        raise ClosedWorldViolation("request URL does not match the adapter template")
    limit = int(match.group("limit"))
    if not 1 <= limit <= adapter["maximum_limit"]:
        raise ClosedWorldViolation("request URL limit is outside the adapter budget")


def plan_request(
    query: str,
    target_source_id: str,
    registry_release_id: str,
    *,
    limit: int | None = None,
    mode: str = "registry_closed",
    contract: dict | None = None,
    sources: dict[str, dict] | None = None,
) -> dict:
    """Create one allowlisted GET request or a terminal NO_SEARCH_ADAPTER receipt."""
    contract = contract or load_json(ROUTING_PATH)
    sources = sources or load_sources()
    if mode not in contract["modes"]:
        raise ClosedWorldViolation(f"unknown search mode: {mode}")
    if not isinstance(registry_release_id, str) or not SHA_RE.fullmatch(registry_release_id):
        raise ClosedWorldViolation("registry_release_id must be a full commit SHA")
    if target_source_id not in sources:
        raise ClosedWorldViolation(f"unknown registry source: {target_source_id}")
    if sources[target_source_id].get("status") != "active":
        raise ClosedWorldViolation(f"source is not active: {target_source_id}")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be non-empty")

    adapter = _adapter_map(contract).get(target_source_id)
    if adapter is None:
        return {
            "registry_release_id": registry_release_id,
            "routing_sha256": routing_sha256(),
            "mode": mode,
            "adapter_id": None,
            "provider_source_id": None,
            "target_source_id": target_source_id,
            "request_url": None,
            "observed_url": None,
            "redirect_chain": [],
            "http_status": None,
            "content_type": None,
            "parser": None,
            "observed_at": None,
            "dedupe_key": None,
            "status": "NO_SEARCH_ADAPTER",
        }

    request_limit = adapter["default_limit"] if limit is None else limit
    if not isinstance(request_limit, int) or not 1 <= request_limit <= adapter["maximum_limit"]:
        raise ValueError("limit outside adapter policy budget")
    if adapter["target_source_policy"] != "same_as_provider":
        raise ClosedWorldViolation("v1 does not permit undeclared provider/target delegation")

    encoded = quote(query.strip(), safe="", encoding="utf-8", errors="strict")
    request_url = adapter["endpoint_template"].replace("{query}", encoded).replace(
        "{limit}", str(request_limit)
    )
    _assert_allowed_url(request_url, adapter)
    _assert_request_matches_template(request_url, adapter)
    return {
        "registry_release_id": registry_release_id,
        "routing_sha256": routing_sha256(),
        "mode": mode,
        "adapter_id": adapter["adapter_id"],
        "provider_source_id": adapter["source_id"],
        "target_source_id": target_source_id,
        "request_url": request_url,
        "parser": adapter["parser"],
        "accepted_content_types": adapter["accepted_content_types"],
        "allowed_hosts": adapter["allowed_hosts"],
        "terminal_status": None,
    }


def classify_receipt(
    plan: dict,
    *,
    observed_url: str,
    redirect_chain: list[str],
    http_status: int,
    content_type: str,
    parse_succeeded: bool,
    result_count: int | None,
    observed_at: str,
    dedupe_key: str | None,
) -> dict:
    """Classify observed network facts without converting failures into zero results."""
    if plan.get("status") == "NO_SEARCH_ADAPTER":
        return plan
    adapter = {
        "allowed_hosts": plan["allowed_hosts"],
    }
    try:
        _assert_allowed_url(plan["request_url"], adapter)
        _assert_allowed_url(observed_url, adapter)
        for url in redirect_chain:
            _assert_allowed_url(url, adapter)
    except ClosedWorldViolation:
        status = "CLOSED_WORLD_VIOLATION"
    else:
        normalized_type = (content_type or "").split(";", 1)[0].strip().lower()
        accepted = {value.lower() for value in plan["accepted_content_types"]}
        if not isinstance(http_status, int) or not 200 <= http_status < 300:
            status = "SOURCE_FETCH_GAP"
        elif normalized_type not in accepted:
            status = "SOURCE_FETCH_GAP"
        elif not parse_succeeded or not isinstance(result_count, int) or result_count < 0:
            status = "SOURCE_FETCH_GAP"
        elif result_count == 0:
            status = "NO_RESULTS"
        else:
            status = "SUCCESS"

    trace = {
        "registry_release_id": plan["registry_release_id"],
        "routing_sha256": plan["routing_sha256"],
        "mode": plan["mode"],
        "adapter_id": plan["adapter_id"],
        "provider_source_id": plan["provider_source_id"],
        "target_source_id": plan["target_source_id"],
        "request_url": plan["request_url"],
        "observed_url": observed_url,
        "redirect_chain": redirect_chain,
        "http_status": http_status,
        "content_type": content_type,
        "parser": plan["parser"],
        "observed_at": observed_at,
        "dedupe_key": dedupe_key,
        "status": status,
    }
    validate_trace(trace)
    return trace


def validate_trace(
    trace: dict,
    contract: dict | None = None,
    *,
    expected_routing_sha256: str | None = None,
    sources: dict[str, dict] | None = None,
) -> None:
    contract = contract or load_json(ROUTING_PATH)
    sources = sources or load_sources()
    missing = set(contract["trace_required_fields"]) - set(trace)
    if missing:
        raise ClosedWorldViolation(f"trace missing required fields: {sorted(missing)}")
    if trace.get("status") not in contract["terminal_statuses"]:
        raise ClosedWorldViolation(f"non-terminal or unknown status: {trace.get('status')}")
    if not isinstance(trace.get("registry_release_id"), str) or not SHA_RE.fullmatch(trace["registry_release_id"]):
        raise ClosedWorldViolation("trace registry_release_id is not a full lowercase commit SHA")
    expected_digest = expected_routing_sha256 or routing_sha256()
    if not SHA256_RE.fullmatch(expected_digest) or trace.get("routing_sha256") != expected_digest:
        raise ClosedWorldViolation("trace routing digest does not match the pinned routing file")
    if trace.get("mode") not in contract["modes"]:
        raise ClosedWorldViolation("trace uses an unknown search mode")

    target_source_id = trace.get("target_source_id")
    target = sources.get(target_source_id)
    if target is None or target.get("status") != "active":
        raise ClosedWorldViolation("trace target is not an active registered source")

    if trace["status"] == "NO_SEARCH_ADAPTER":
        empty_fields = (
            "adapter_id", "provider_source_id", "request_url", "observed_url",
            "http_status", "content_type", "parser", "observed_at", "dedupe_key",
        )
        if any(trace.get(field) is not None for field in empty_fields):
            raise ClosedWorldViolation("NO_SEARCH_ADAPTER trace must not claim a provider request")
        if trace.get("redirect_chain") != []:
            raise ClosedWorldViolation("NO_SEARCH_ADAPTER trace must not claim observed redirects")
        if target_source_id in _adapter_map(contract):
            raise ClosedWorldViolation("NO_SEARCH_ADAPTER trace contradicts a published adapter")
        return

    adapter = next(
        (item for item in contract["adapters"] if item["adapter_id"] == trace.get("adapter_id")),
        None,
    )
    if adapter is None:
        raise ClosedWorldViolation("trace references an unknown adapter")
    if trace.get("provider_source_id") != adapter["source_id"]:
        raise ClosedWorldViolation("trace provider does not match the adapter source")
    if adapter["target_source_policy"] == "same_as_provider" and target_source_id != adapter["source_id"]:
        raise ClosedWorldViolation("trace target does not match the v1 provider")
    if trace.get("parser") != adapter["parser"]:
        raise ClosedWorldViolation("trace parser does not match the adapter")
    _assert_allowed_url(trace.get("request_url"), adapter)
    _assert_request_matches_template(trace["request_url"], adapter)

    network_violation = False
    observed_urls = [trace.get("observed_url"), *(trace.get("redirect_chain") or [])]
    for url in observed_urls:
        try:
            _assert_allowed_url(url, adapter)
        except (ClosedWorldViolation, TypeError):
            network_violation = True
    if network_violation and trace["status"] != "CLOSED_WORLD_VIOLATION":
        raise ClosedWorldViolation("trace observes a forbidden host without a violation status")
    if trace["status"] in {"SUCCESS", "NO_RESULTS"}:
        if not isinstance(trace.get("http_status"), int) or not 200 <= trace["http_status"] < 300:
            raise ClosedWorldViolation("successful trace has a non-successful HTTP status")
        normalized_type = str(trace.get("content_type") or "").split(";", 1)[0].strip().lower()
        if normalized_type not in {item.lower() for item in adapter["accepted_content_types"]}:
            raise ClosedWorldViolation("successful trace has an unaccepted Content-Type")
    if trace["status"] == "SUCCESS" and not trace.get("dedupe_key"):
        raise ClosedWorldViolation("successful trace must preserve a dedupe key")
