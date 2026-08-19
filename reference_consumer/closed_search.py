#!/usr/bin/env python3
"""Pure helpers for registry-derived brokered and direct OA search contracts.

This module performs no network requests. It demonstrates how a chatbot can
derive a domain-restricted search route from any selected registry source,
reject escaped candidate URLs, and classify original-source receipts without
treating search snippets as evidence.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
ROUTING_PATH = ROOT / "data" / "chatbot-search-routing.json"
MANIFEST_PATH = ROOT / "data" / "registry-manifest.json"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
HOST_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)
ORIGINAL_CONTENT_TYPES = (
    "text/html",
    "application/pdf",
    "application/xml",
    "text/xml",
    "application/json",
    "application/atom+xml",
)


class ClosedWorldViolation(ValueError):
    """Raised when a source, route, receipt, or URL escapes the pinned registry."""


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


def _resolve_digest(value: str | None) -> str:
    digest = routing_sha256() if value is None else value
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        raise ClosedWorldViolation("routing digest must be a lowercase SHA-256")
    return digest


def _adapter_map(contract: dict) -> dict[str, dict]:
    return {adapter["source_id"]: adapter for adapter in contract["adapters"]}


def _canonical_host(source: dict) -> str:
    parsed = urlparse(str(source.get("canonical_url", "")))
    try:
        explicit_port = parsed.port is not None
    except ValueError as exc:
        raise ClosedWorldViolation("source canonical URL contains an invalid port") from exc
    host = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or not HOST_RE.fullmatch(host)
        or parsed.username
        or parsed.password
        or parsed.fragment
        or explicit_port
    ):
        raise ClosedWorldViolation("source lacks a safe HTTPS canonical search route")
    if host == "localhost" or host.endswith(".localhost"):
        raise ClosedWorldViolation("source canonical host cannot be local")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ClosedWorldViolation("source canonical host cannot be an IP literal")
    return host


def _shared_canonical_host(source_id: str, sources: dict[str, dict]) -> bool:
    selected = sources[source_id]
    host = _canonical_host(selected)
    matches = 0
    for source in sources.values():
        if source.get("status") != "active":
            continue
        try:
            candidate = _canonical_host(source)
        except ClosedWorldViolation:
            continue
        if candidate == host:
            matches += 1
    return matches > 1


def _assert_safe_path(url: str) -> None:
    parsed = urlparse(url)
    lowered = parsed.path.lower()
    if "\\" in url or any(token in lowered for token in ("%2f", "%5c", "%2e")):
        raise ClosedWorldViolation(f"URL contains encoded or backslash path traversal: {url}")
    decoded = unquote(parsed.path)
    if any(part in {".", ".."} for part in decoded.split("/")):
        raise ClosedWorldViolation(f"URL contains a dot-segment path: {url}")


def _assert_allowed_url(url: str, allowed_hosts: list[str]) -> None:
    if not isinstance(url, str):
        raise ClosedWorldViolation("URL must be a string")
    parsed = urlparse(url)
    try:
        explicit_port = parsed.port is not None
    except ValueError as exc:
        raise ClosedWorldViolation(f"URL contains an invalid port: {url}") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname not in allowed_hosts
        or parsed.username
        or parsed.password
        or parsed.fragment
        or explicit_port
    ):
        raise ClosedWorldViolation(f"URL outside exact source allowlist: {url}")
    _assert_safe_path(url)


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


def _base_trace(
    *,
    release_id: str,
    digest: str,
    mode: str,
    target_source_id: str,
    query: str,
) -> dict:
    return {
        "registry_release_id": release_id,
        "main_ref_commit_sha": release_id,
        "routing_sha256": digest,
        "mode": mode,
        "discovery_method": None,
        "broker_id": None,
        "broker_operation": None,
        "broker_query": query,
        "broker_domains": [],
        "broker_result_count": None,
        "source_route_id": None,
        "adapter_id": None,
        "provider_source_id": None,
        "target_source_id": target_source_id,
        "candidate_url": None,
        "candidate_identity_status": None,
        "request_url": None,
        "observed_url": None,
        "redirect_chain": [],
        "http_status": None,
        "content_type": None,
        "parser": None,
        "source_identity_verified": None,
        "original_record_observed": None,
        "evidence_class": None,
        "observed_at": None,
        "dedupe_key": None,
        "status": None,
    }


def _validate_selection(
    query: str,
    target_source_id: str,
    registry_release_id: str,
    contract: dict,
    sources: dict[str, dict],
    mode: str,
) -> dict:
    if mode not in contract["modes"]:
        raise ClosedWorldViolation(f"unknown search mode: {mode}")
    if not isinstance(registry_release_id, str) or not SHA_RE.fullmatch(registry_release_id):
        raise ClosedWorldViolation("registry_release_id must be a full commit SHA")
    source = sources.get(target_source_id)
    if source is None:
        raise ClosedWorldViolation(f"unknown registry source: {target_source_id}")
    if source.get("status") != "active":
        raise ClosedWorldViolation(f"source is not active: {target_source_id}")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be non-empty")
    return source


def plan_brokered_search(
    query: str,
    target_source_id: str,
    registry_release_id: str,
    *,
    limit: int | None = None,
    contract: dict | None = None,
    sources: dict[str, dict] | None = None,
    routing_digest: str | None = None,
) -> dict:
    """Derive a domain-restricted web-search plan from any active registry source."""
    contract = contract or load_json(ROUTING_PATH)
    sources = sources or load_sources()
    source = _validate_selection(
        query, target_source_id, registry_release_id, contract, sources, "registry_brokered"
    )
    digest = _resolve_digest(routing_digest)
    plan = _base_trace(
        release_id=registry_release_id,
        digest=digest,
        mode="registry_brokered",
        target_source_id=target_source_id,
        query=query.strip(),
    )
    if "discovery" not in source.get("access_roles", []):
        plan["status"] = "NO_CANONICAL_SEARCH_ROUTE"
        return plan
    try:
        host = _canonical_host(source)
    except ClosedWorldViolation:
        plan["status"] = "NO_CANONICAL_SEARCH_ROUTE"
        return plan

    broker = contract["brokered_discovery"]
    result_limit = broker["maximum_results_per_source"] if limit is None else limit
    if not isinstance(result_limit, int) or not 1 <= result_limit <= broker["maximum_results_per_source"]:
        raise ValueError("limit outside broker policy budget")

    source_name = source["name"].strip()
    plan.update(
        {
            "discovery_method": "domain_restricted_web_search",
            "broker_id": broker["broker_id"],
            "broker_operation": broker["operation"],
            "broker_query": f'{query.strip()} "{source_name}"',
            "broker_domains": [host],
            "source_route_id": f"registry:{target_source_id}",
            "provider_source_id": target_source_id,
            "allowed_hosts": [host],
            "accepted_content_types": list(ORIGINAL_CONTENT_TYPES),
            "parser": (
                "registry_metadata_record_v1"
                if source.get("oa_scope") == "metadata_only" or "fulltext" not in source.get("access_roles", [])
                else "registered_source_document_v1"
            ),
            "evidence_scope": (
                "metadata_only"
                if source.get("oa_scope") == "metadata_only" or "fulltext" not in source.get("access_roles", [])
                else "fulltext_candidate"
            ),
            "source_name": source_name,
            "canonical_path_hint": urlparse(source["canonical_url"]).path or "/",
            "shared_host": _shared_canonical_host(target_source_id, sources),
            "maximum_results": result_limit,
            "terminal_status": None,
        }
    )
    return plan


def classify_broker_search(
    plan: dict,
    *,
    candidate_urls: list[str] | None,
    observed_at: str,
    broker_succeeded: bool = True,
) -> dict:
    """Classify the broker stage without treating snippets as evidence."""
    if plan.get("status") == "NO_CANONICAL_SEARCH_ROUTE":
        return plan
    trace = {key: plan.get(key) for key in load_json(ROUTING_PATH)["trace_required_fields"]}
    trace["broker_result_count"] = None if candidate_urls is None else len(candidate_urls)
    trace["observed_at"] = observed_at
    if not broker_succeeded or candidate_urls is None:
        trace["status"] = "SEARCH_BROKER_GAP"
    elif not candidate_urls:
        trace["status"] = "NO_RESULTS"
    else:
        raise ValueError("non-empty broker results must be classified per candidate")
    validate_trace(trace)
    return trace


def accept_brokered_candidate(plan: dict, candidate_url: str) -> dict:
    """Accept a broker result only when its URL remains on the selected source host."""
    if plan.get("status") == "NO_CANONICAL_SEARCH_ROUTE":
        return plan
    _assert_allowed_url(candidate_url, plan["allowed_hosts"])
    fetch_plan = dict(plan)
    fetch_plan.update(
        {
            "candidate_url": candidate_url,
            "candidate_identity_status": "HOST_ACCEPTED_IDENTITY_PENDING",
            "request_url": candidate_url,
        }
    )
    return fetch_plan


def classify_brokered_receipt(
    plan: dict,
    *,
    observed_url: str,
    redirect_chain: list[str],
    http_status: int,
    content_type: str,
    parse_succeeded: bool,
    source_identity_verified: bool,
    original_record_observed: bool,
    observed_at: str,
    dedupe_key: str | None,
    evidence_class: str,
    broker_result_count: int = 1,
) -> dict:
    """Classify one original-source fetch after registry-derived broker discovery."""
    if not plan.get("candidate_url"):
        raise ClosedWorldViolation("brokered receipt lacks an accepted candidate URL")
    if not isinstance(broker_result_count, int) or broker_result_count < 1:
        raise ValueError("broker_result_count must be positive for a candidate receipt")

    try:
        _assert_allowed_url(plan["candidate_url"], plan["allowed_hosts"])
        _assert_allowed_url(plan["request_url"], plan["allowed_hosts"])
        _assert_allowed_url(observed_url, plan["allowed_hosts"])
        for url in redirect_chain:
            _assert_allowed_url(url, plan["allowed_hosts"])
    except ClosedWorldViolation:
        status = "CLOSED_WORLD_VIOLATION"
    else:
        normalized_type = (content_type or "").split(";", 1)[0].strip().lower()
        accepted = {value.lower() for value in plan["accepted_content_types"]}
        if not isinstance(http_status, int) or not 200 <= http_status < 300:
            status = "ORIGINAL_FETCH_GAP"
        elif normalized_type not in accepted or not parse_succeeded:
            status = "ORIGINAL_FETCH_GAP"
        elif not original_record_observed or evidence_class == "discovery_snippet":
            status = "ORIGINAL_FETCH_GAP"
        elif not source_identity_verified:
            status = "SOURCE_IDENTITY_GAP"
        elif plan["evidence_scope"] == "metadata_only" and evidence_class == "original_fulltext":
            status = "FULLTEXT_NOT_AUTHORIZED"
        elif evidence_class not in {"registry_metadata", "original_fulltext"}:
            status = "ORIGINAL_FETCH_GAP"
        else:
            status = "SUCCESS"

    trace = {
        "registry_release_id": plan["registry_release_id"],
        "main_ref_commit_sha": plan["main_ref_commit_sha"],
        "routing_sha256": plan["routing_sha256"],
        "mode": "registry_brokered",
        "discovery_method": plan["discovery_method"],
        "broker_id": plan["broker_id"],
        "broker_operation": plan["broker_operation"],
        "broker_query": plan["broker_query"],
        "broker_domains": plan["broker_domains"],
        "broker_result_count": broker_result_count,
        "source_route_id": plan["source_route_id"],
        "adapter_id": None,
        "provider_source_id": plan["provider_source_id"],
        "target_source_id": plan["target_source_id"],
        "candidate_url": plan["candidate_url"],
        "candidate_identity_status": (
            "VERIFIED" if source_identity_verified else "UNVERIFIED"
        ),
        "request_url": plan["request_url"],
        "observed_url": observed_url,
        "redirect_chain": redirect_chain,
        "http_status": http_status,
        "content_type": content_type,
        "parser": plan["parser"],
        "source_identity_verified": source_identity_verified,
        "original_record_observed": original_record_observed,
        "evidence_class": evidence_class,
        "observed_at": observed_at,
        "dedupe_key": dedupe_key,
        "status": status,
    }
    validate_trace(trace)
    return trace


def plan_request(
    query: str,
    target_source_id: str,
    registry_release_id: str,
    *,
    limit: int | None = None,
    mode: str = "registry_closed",
    contract: dict | None = None,
    sources: dict[str, dict] | None = None,
    routing_digest: str | None = None,
) -> dict:
    """Create one strict direct-adapter GET request or a no-adapter receipt."""
    contract = contract or load_json(ROUTING_PATH)
    sources = sources or load_sources()
    _validate_selection(query, target_source_id, registry_release_id, contract, sources, mode)
    digest = _resolve_digest(routing_digest)
    adapter = _adapter_map(contract).get(target_source_id)
    if adapter is None:
        trace = _base_trace(
            release_id=registry_release_id,
            digest=digest,
            mode=mode,
            target_source_id=target_source_id,
            query=query.strip(),
        )
        trace.update({"discovery_method": "direct_adapter", "status": "NO_SEARCH_ADAPTER"})
        return trace

    request_limit = adapter["default_limit"] if limit is None else limit
    if not isinstance(request_limit, int) or not 1 <= request_limit <= adapter["maximum_limit"]:
        raise ValueError("limit outside adapter policy budget")
    if adapter["target_source_policy"] != "same_as_provider":
        raise ClosedWorldViolation("direct adapters do not permit undeclared provider delegation")

    encoded = quote(query.strip(), safe="", encoding="utf-8", errors="strict")
    request_url = adapter["endpoint_template"].replace("{query}", encoded).replace(
        "{limit}", str(request_limit)
    )
    _assert_allowed_url(request_url, adapter["allowed_hosts"])
    _assert_request_matches_template(request_url, adapter)
    return {
        "registry_release_id": registry_release_id,
        "main_ref_commit_sha": registry_release_id,
        "routing_sha256": digest,
        "mode": mode,
        "discovery_method": "direct_adapter",
        "broker_id": None,
        "broker_operation": None,
        "broker_query": query.strip(),
        "broker_domains": [],
        "broker_result_count": None,
        "source_route_id": None,
        "adapter_id": adapter["adapter_id"],
        "provider_source_id": adapter["source_id"],
        "target_source_id": target_source_id,
        "candidate_url": None,
        "candidate_identity_status": None,
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
    """Classify strict-adapter network facts without rewriting failures as zero results."""
    if plan.get("status") == "NO_SEARCH_ADAPTER":
        return plan
    try:
        _assert_allowed_url(plan["request_url"], plan["allowed_hosts"])
        _assert_allowed_url(observed_url, plan["allowed_hosts"])
        for url in redirect_chain:
            _assert_allowed_url(url, plan["allowed_hosts"])
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
        "main_ref_commit_sha": plan["main_ref_commit_sha"],
        "routing_sha256": plan["routing_sha256"],
        "mode": plan["mode"],
        "discovery_method": "direct_adapter",
        "broker_id": None,
        "broker_operation": None,
        "broker_query": plan["broker_query"],
        "broker_domains": [],
        "broker_result_count": result_count,
        "source_route_id": None,
        "adapter_id": plan["adapter_id"],
        "provider_source_id": plan["provider_source_id"],
        "target_source_id": plan["target_source_id"],
        "candidate_url": None,
        "candidate_identity_status": None,
        "request_url": plan["request_url"],
        "observed_url": observed_url,
        "redirect_chain": redirect_chain,
        "http_status": http_status,
        "content_type": content_type,
        "parser": plan["parser"],
        "source_identity_verified": True,
        "original_record_observed": False,
        "evidence_class": "registry_metadata",
        "observed_at": observed_at,
        "dedupe_key": dedupe_key,
        "status": status,
    }
    validate_trace(trace)
    return trace


def validate_connector_bootstrap(
    *,
    main_ref_commit_sha: str,
    release_index: dict,
    release_manifest: dict,
    fetched_git_blob_sha1: dict[str, str],
    fetched_release_manifest_sha256: str | None = None,
    contract: dict | None = None,
) -> None:
    """Validate the connector chain from current main to immutable release files.

    GitHub's file response supplies the Git blob SHA-1.  A host that can also
    hash the fetched manifest may pass ``fetched_release_manifest_sha256`` for
    the additional checksum comparison; connector-only chatbots can still
    authenticate the same bytes through the published Git blob identity.
    """
    contract = contract or load_json(ROUTING_PATH)
    if not SHA_RE.fullmatch(str(main_ref_commit_sha)):
        raise ClosedWorldViolation("main ref is not a full commit SHA")
    if release_index.get("current_release_id") != main_ref_commit_sha:
        raise ClosedWorldViolation("release index does not match the current main ref")
    matching_entries = [
        entry
        for entry in release_index.get("releases", [])
        if entry.get("release_id") == main_ref_commit_sha
    ]
    if len(matching_entries) != 1:
        raise ClosedWorldViolation("release index lacks one current-release entry")
    current_entry = matching_entries[0]
    if (
        release_manifest.get("schema_version") != "4.0.0"
        or current_entry.get("commit_sha") != main_ref_commit_sha
        or release_manifest.get("release_id") != main_ref_commit_sha
        or release_manifest.get("commit_sha") != main_ref_commit_sha
    ):
        raise ClosedWorldViolation("release manifest does not match the current main ref")
    if release_manifest.get("repository_main_ref_api") != contract["bootstrap"]["main_ref_api"]:
        raise ClosedWorldViolation("release manifest uses a different main-ref bootstrap")
    identity_pairs = {
        "chatbot_search_protocol_version": contract.get("protocol_version"),
        "chatbot_search_method": contract.get("method"),
        "chatbot_search_schema_version": contract.get("schema_version"),
        "chatbot_search_default_mode": contract.get("default_mode"),
        "chatbot_search_brokered_source_count": contract.get("brokered_discovery", {}).get(
            "eligible_source_count"
        ),
        "chatbot_search_adapter_count": len(contract.get("adapters", [])),
    }
    for field, expected in identity_pairs.items():
        if release_manifest.get(field) != expected or current_entry.get(field) != expected:
            raise ClosedWorldViolation(f"release chatbot-search identity mismatch: {field}")
    required = contract["bootstrap"]["required_files"]
    observed_manifest_sha = fetched_git_blob_sha1.get("release-manifest.json")
    if not isinstance(observed_manifest_sha, str) or not SHA1_RE.fullmatch(observed_manifest_sha):
        raise ClosedWorldViolation("connector did not preserve the release-manifest Git blob SHA")
    if current_entry.get("manifest_git_blob_sha1") != observed_manifest_sha:
        raise ClosedWorldViolation("release-manifest Git blob identity does not match the release index")
    indexed_manifest_sha256 = current_entry.get("manifest_sha256")
    if not isinstance(indexed_manifest_sha256, str) or not SHA256_RE.fullmatch(indexed_manifest_sha256):
        raise ClosedWorldViolation("release index lacks the release-manifest SHA-256")
    if fetched_release_manifest_sha256 is not None:
        if (
            not isinstance(fetched_release_manifest_sha256, str)
            or not SHA256_RE.fullmatch(fetched_release_manifest_sha256)
            or fetched_release_manifest_sha256 != indexed_manifest_sha256
        ):
            raise ClosedWorldViolation("release-manifest SHA-256 does not match the release index")
    for name in required:
        observed = fetched_git_blob_sha1.get(name)
        if not isinstance(observed, str) or not SHA1_RE.fullmatch(observed):
            raise ClosedWorldViolation(f"connector did not preserve the Git blob SHA for {name}")
        if name == "release-manifest.json":
            continue
        metadata = release_manifest.get("files", {}).get(name)
        if not isinstance(metadata, dict) or metadata.get("git_blob_sha1") != observed:
            raise ClosedWorldViolation(f"Git blob identity mismatch for {name}")
        if not SHA256_RE.fullmatch(str(metadata.get("sha256", ""))):
            raise ClosedWorldViolation(f"manifest lacks a SHA-256 for {name}")


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
    release_id = trace.get("registry_release_id")
    if not isinstance(release_id, str) or not SHA_RE.fullmatch(release_id):
        raise ClosedWorldViolation("trace registry_release_id is not a full lowercase commit SHA")
    if trace.get("main_ref_commit_sha") != release_id:
        raise ClosedWorldViolation("current-search trace does not match the main ref commit")
    expected_digest = expected_routing_sha256 or routing_sha256()
    if not SHA256_RE.fullmatch(expected_digest) or trace.get("routing_sha256") != expected_digest:
        raise ClosedWorldViolation("trace routing digest does not match the pinned routing file")
    mode = trace.get("mode")
    if mode not in contract["modes"]:
        raise ClosedWorldViolation("trace uses an unknown search mode")

    target_source_id = trace.get("target_source_id")
    target = sources.get(target_source_id)
    if target is None or target.get("status") != "active":
        raise ClosedWorldViolation("trace target is not an active registered source")

    if trace["status"] in {"NO_SEARCH_ADAPTER", "NO_CANONICAL_SEARCH_ROUTE"}:
        if trace["status"] == "NO_SEARCH_ADAPTER" and mode not in {"registry_closed", "direct_only"}:
            raise ClosedWorldViolation("NO_SEARCH_ADAPTER is valid only in a strict direct mode")
        if trace["status"] == "NO_CANONICAL_SEARCH_ROUTE" and mode != "registry_brokered":
            raise ClosedWorldViolation("NO_CANONICAL_SEARCH_ROUTE is valid only in brokered mode")
        empty_fields = (
            "adapter_id", "provider_source_id", "candidate_url", "request_url",
            "observed_url", "http_status", "content_type", "parser", "observed_at",
            "dedupe_key", "source_identity_verified", "original_record_observed",
            "evidence_class",
        )
        if any(trace.get(field) is not None for field in empty_fields):
            raise ClosedWorldViolation("no-route trace must not claim a provider or network receipt")
        if trace.get("redirect_chain") != [] or trace.get("broker_domains") != []:
            raise ClosedWorldViolation("no-route trace must not claim domains or redirects")
        if trace["status"] == "NO_SEARCH_ADAPTER" and target_source_id in _adapter_map(contract):
            raise ClosedWorldViolation("NO_SEARCH_ADAPTER contradicts a published direct adapter")
        return

    if mode == "registry_brokered":
        brokered_statuses = {
            "SUCCESS", "NO_RESULTS", "NO_CANONICAL_SEARCH_ROUTE",
            "SEARCH_BROKER_GAP", "SOURCE_IDENTITY_GAP", "ORIGINAL_FETCH_GAP",
            "FULLTEXT_NOT_AUTHORIZED", "CLOSED_WORLD_VIOLATION",
        }
        if trace["status"] not in brokered_statuses:
            raise ClosedWorldViolation("brokered trace uses a strict-adapter-only status")
        if trace.get("discovery_method") != "domain_restricted_web_search":
            raise ClosedWorldViolation("brokered trace lacks the declared discovery method")
        broker = contract["brokered_discovery"]
        if trace.get("broker_id") != broker["broker_id"] or trace.get("broker_operation") != broker["operation"]:
            raise ClosedWorldViolation("brokered trace uses an undeclared broker")
        host = _canonical_host(target)
        if trace.get("broker_domains") != [host]:
            raise ClosedWorldViolation("broker domains do not equal the selected source canonical host")
        if trace.get("source_route_id") != f"registry:{target_source_id}":
            raise ClosedWorldViolation("brokered trace route was not derived from the selected source")
        if trace.get("provider_source_id") != target_source_id:
            raise ClosedWorldViolation("original provider does not equal the selected source")
        if trace.get("adapter_id") is not None:
            raise ClosedWorldViolation("brokered trace cannot claim a direct adapter")
        if f'"{target["name"]}"' not in str(trace.get("broker_query", "")):
            raise ClosedWorldViolation("broker query does not preserve the exact registered source name")

        if trace["status"] in {"NO_RESULTS", "SEARCH_BROKER_GAP"}:
            if trace.get("candidate_url") is not None or trace.get("request_url") is not None:
                raise ClosedWorldViolation("broker-only terminal trace cannot claim an origin fetch")
            if trace["status"] == "NO_RESULTS" and trace.get("broker_result_count") != 0:
                raise ClosedWorldViolation("NO_RESULTS requires an observed zero-result broker receipt")
            if trace["status"] == "SEARCH_BROKER_GAP" and trace.get("broker_result_count") is not None:
                raise ClosedWorldViolation("SEARCH_BROKER_GAP cannot claim a result count")
            if not isinstance(trace.get("observed_at"), str) or not trace["observed_at"]:
                raise ClosedWorldViolation("broker receipt must preserve an observation time")
            return

        for url in (trace.get("candidate_url"), trace.get("request_url")):
            _assert_allowed_url(url, [host])
        network_violation = False
        for url in (trace.get("observed_url"), *(trace.get("redirect_chain") or [])):
            try:
                _assert_allowed_url(url, [host])
            except (ClosedWorldViolation, TypeError):
                network_violation = True
        if network_violation:
            if trace["status"] != "CLOSED_WORLD_VIOLATION":
                raise ClosedWorldViolation("brokered trace observes a forbidden host without a violation status")
            return
        if trace["status"] == "CLOSED_WORLD_VIOLATION":
            raise ClosedWorldViolation("brokered trace claims a host violation without a forbidden receipt")
        if not isinstance(trace.get("broker_result_count"), int) or trace["broker_result_count"] < 1:
            raise ClosedWorldViolation("brokered candidate trace requires a positive result count")
        if not isinstance(trace.get("observed_at"), str) or not trace["observed_at"]:
            raise ClosedWorldViolation("original-source receipt must preserve an observation time")
        if trace["status"] == "SUCCESS":
            if trace.get("source_identity_verified") is not True:
                raise ClosedWorldViolation("successful brokered trace lacks source identity proof")
            if trace.get("original_record_observed") is not True:
                raise ClosedWorldViolation("successful brokered trace lacks an original record")
            if trace.get("evidence_class") not in {"registry_metadata", "original_fulltext"}:
                raise ClosedWorldViolation("successful brokered trace has an invalid evidence class")
            if not trace.get("dedupe_key"):
                raise ClosedWorldViolation("successful brokered trace must preserve a dedupe key")
        if target.get("oa_scope") == "metadata_only" and trace.get("evidence_class") == "original_fulltext":
            if trace["status"] != "FULLTEXT_NOT_AUTHORIZED":
                raise ClosedWorldViolation("metadata-only source was upgraded to full text")
        if trace.get("evidence_class") == "discovery_snippet" and trace["status"] != "ORIGINAL_FETCH_GAP":
            raise ClosedWorldViolation("search snippets cannot become evidence")
        if trace["status"] == "SOURCE_IDENTITY_GAP" and trace.get("source_identity_verified") is not False:
            raise ClosedWorldViolation("SOURCE_IDENTITY_GAP requires an unverified source identity")
        return

    direct_statuses = {
        "SUCCESS", "NO_RESULTS", "NO_SEARCH_ADAPTER", "SOURCE_FETCH_GAP",
        "CLOSED_WORLD_VIOLATION",
    }
    if trace["status"] not in direct_statuses:
        raise ClosedWorldViolation("strict direct trace uses a broker-only status")
    adapter = next(
        (item for item in contract["adapters"] if item["adapter_id"] == trace.get("adapter_id")),
        None,
    )
    if adapter is None:
        raise ClosedWorldViolation("trace references an unknown adapter")
    if trace.get("provider_source_id") != adapter["source_id"]:
        raise ClosedWorldViolation("trace provider does not match the adapter source")
    if adapter["target_source_policy"] == "same_as_provider" and target_source_id != adapter["source_id"]:
        raise ClosedWorldViolation("trace target does not match the direct provider")
    if trace.get("parser") != adapter["parser"]:
        raise ClosedWorldViolation("trace parser does not match the adapter")
    _assert_allowed_url(trace.get("request_url"), adapter["allowed_hosts"])
    _assert_request_matches_template(trace["request_url"], adapter)
    network_violation = False
    for url in [trace.get("observed_url"), *(trace.get("redirect_chain") or [])]:
        try:
            _assert_allowed_url(url, adapter["allowed_hosts"])
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
