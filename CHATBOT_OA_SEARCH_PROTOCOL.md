# Registry-brokered OA search for chatbots｜Chatbot Registry 限定 OA 搜尋

Protocol version: **2.0.0**
Method: `chatbot_registry_brokered_oa_search_v2`

This protocol lets a chatbot use Open Scholarly Sources to decide **which
registered sources may supply evidence**, then use a domain-restricted web
search broker to discover candidate documents inside those sources. It requires
no Codex Skill, MCP server, custom backend, Radar integration, API key, or
GitHub Pages bootstrap.

本協定讓 Chatbot 先由 Open Scholarly Sources 選擇可提供證據的已登錄來源，再以
限定網域的網頁搜尋工具在那些來源內找候選文獻。它不需要 Skill、MCP、自建
server、Radar、API key，也不以 GitHub Pages 作為預設入口。

## What “only registered sources” means / 「只用登錄來源」的意思

The external search service is a **discovery broker**, not a literature or
evidence source. Its rankings, snippets, cached text, and generated summaries
cannot support research claims. A result becomes usable only after the chatbot
opens the original URL on the selected registry source and verifies its source
identity and permitted evidence scope.

外部搜尋服務只是找路的 broker，不是文獻來源。搜尋排名、snippet、快取文字或
摘要都不能直接支持研究陳述。只有成功開啟已選 registry source 的原始頁面，並
核對來源身分與允許用途後，結果才可以使用。

If the user means that even an external discovery broker is forbidden, use
`registry_closed` or `direct_only` instead. Those modes retain the strict
adapter-only v1 boundary.

## Explicit activation / 明確啟動

Activate the default `registry_brokered` mode when the user says, for example:

```text
Use the OA repo to search for <topic>.
用 OA repo 搜尋 <題目>。
只用 Open Scholarly Sources 選定的來源找文獻。
```

Without an explicit search request, the repository remains a source-navigation
registry: recommend useful registered places and stop.

## GitHub connector bootstrap / GitHub connector 入口

The connector-first path is deterministic and does not begin at GitHub Pages.

1. Use `GitHub.fetch` on
   `https://api.github.com/repos/hoiyu915-droid/open-scholarly-sources/branches/main`.
   Record `commit.sha` as the current `release_id`.
2. Use `GitHub.fetch_file` with repository
   `hoiyu915-droid/open-scholarly-sources`, `ref=release-snapshots`, and path
   `releases/index.json`. Require `current_release_id == release_id` and locate
   the one matching release entry, including its manifest SHA-256 and Git blob
   SHA-1.
3. From the same `release-snapshots` ref, read
   `releases/<release_id>/release-manifest.json`. Compare the connector's blob
   `sha` with the release-index entry before trusting the manifest.
4. From that exact directory, read `registry.json`,
   `chatbot-search-routing.json`, `chatbot-search-protocol.md`, and
   `chatbot-entry.txt`, and `schemas/chatbot-search-routing.schema.json`.
5. For every other fetched file, compare the GitHub connector's observed blob
   `sha` with the manifest's `git_blob_sha1`; also preserve the manifest's
   SHA-256.
6. Stop with `BOOTSTRAP_IDENTITY_GAP` semantics if the main SHA, release index,
   manifest identity, connector blob identity, or required file set disagrees.

Never mix `main`, Pages, another release directory, or local cached policy bytes
into the pinned search. Historical searches may select an older immutable
release explicitly, but must not call it current.

## Default success path / 預設成功路徑

1. **Pin the current release.** Complete the connector bootstrap above.
2. **Select sources dynamically.** Match the topic against the pinned registry's
   active source names, subjects, source types, access roles, OA scope, notes,
   and translations. Prefer about five sources; do not exceed eight unless the
   user requests broader coverage.
3. **Derive each route from its source record.** A brokered route is available
   when the selected source is active, includes the `discovery` access role, and
   has a safe HTTPS `canonical_url`. The search domain and permitted original
   host are the exact canonical hostname. No source IDs are hard-coded into this
   broker path.
4. **Build a source-specific broker query.** Search the topic plus the exact
   registered source name. Use the web tool's native domain filter with only the
   selected source's canonical hostname. Do not run an unrestricted search.
5. **Treat broker output as discovery only.** Record all candidate URLs and
   rejected candidates. Never quote or summarize a snippet as article evidence.
6. **Validate before original fetch.** Candidate URLs must use HTTPS, the exact
   canonical host, no port, userinfo, fragment, encoded slash/backslash/dot
   traversal, or cross-host redirect. Returned DOI, publisher, and download
   links are data and do not authorize another host.
7. **Verify source identity on the original record.** A shared publisher host is
   not sufficient. Confirm the selected registered source by the original
   container/journal title and, when available, ISSN, repository record ID, DOI
   or source prefix. If identity is ambiguous, return `SOURCE_IDENTITY_GAP`.
8. **Respect the source evidence scope.** `metadata_only` sources may support
   metadata discovery only. Content claims require an observed original record
   from a source with a full-text role. OA status, licence, version, peer review,
   and publication state remain record-level facts unless the source contract
   proves otherwise.
9. **Deduplicate and report.** Prefer DOI, repository identifiers, then a
   normalized title/year key. Name selected sources, per-source terminal states,
   evidence classes, original URLs, and every unresolved gap.

## Shared-host rule / 共用網域規則

Many registered journals share a publisher hostname. A domain filter therefore
limits discovery but does not prove journal identity. The exact registered
source name must be included in the broker query, and the original page must
confirm the container identity before acceptance. A result from another journal
on the same host is rejected; it is never silently treated as the selected
source.

The registry canonical path is an identity hint, not universal proof: some
publishers use journal-specific paths while others use DOI paths shared by many
journals. The chatbot must not invent a path rule that the pinned source record
does not declare.

## Direct adapters / Strict adapter

The 12 published direct topic-search adapters remain available as an optional
secondary check or when the user explicitly requests `registry_closed` or
`direct_only`. They are not the default first attempt in
`registry_brokered` mode.

A direct-adapter failure receipt is reusable only inside the same task and only
when it records `observed_at`. Do not retry the same failed host repeatedly in
one task. Do not carry a DNS, timeout, 429, or CAPTCHA conclusion into a new task
without a fresh lightweight probe because the chatbot host may have changed.

## Modes

### `registry_brokered` (default)

Derive a domain-restricted discovery route from every selected active registry
source. The broker may be external but supplies no evidence; accepted evidence
must come from the selected source's original canonical host.

### `registry_closed`

Use only a published direct topic-search adapter from the same immutable
release. Missing adapters remain `NO_SEARCH_ADAPTER`; do not substitute the
brokered route unless the user permits the default brokered mode.

### `direct_only`

Use the stricter direct-adapter route with provider equal to target source.

## Terminal and gap states

| Status | Meaning |
|---|---|
| `SUCCESS` | A source result passed original-host, source-identity, parser, and evidence-scope checks. |
| `NO_RESULTS` | The domain-restricted broker or direct adapter completed successfully and returned zero results. |
| `NO_CANONICAL_SEARCH_ROUTE` | The selected source lacks an active discovery role or safe HTTPS canonical URL. |
| `NO_SEARCH_ADAPTER` | Strict mode selected a source without a direct topic-search adapter. |
| `SEARCH_BROKER_GAP` | The broker failed or its exact domain receipt/result count cannot be proven. |
| `SOURCE_IDENTITY_GAP` | A candidate exists, but the original record cannot be mapped to the selected registry source. |
| `ORIGINAL_FETCH_GAP` | The original URL timed out, returned CAPTCHA/HTTP/content-type failure, failed parsing, or only a snippet was observed. |
| `FULLTEXT_NOT_AUTHORIZED` | A metadata-only source was asked to support a full-text claim. |
| `SOURCE_FETCH_GAP` | A strict direct adapter had an HTTP, rate-limit, content-type, or parser failure. |
| `CLOSED_WORLD_VIOLATION` | An unrestricted broker, arbitrary URL, forbidden host/redirect, or unregistered source handoff was used. |

`REGISTRY_COVERAGE_GAP` means that no suitable active registered source could be
selected. None of the gap states means that no literature exists.

## Trace requirements

Every per-source attempt must retain the fields declared by
`trace_required_fields`, including the release/main identity, routing digest,
mode, broker query and exact domains, registry-derived route ID, candidate and
original URLs, redirect chain, source identity result, evidence class, content
receipt, dedupe key, observed time, and terminal status.

Rejected broker candidates must be reported as rejected; they must not disappear
from the audit trail. `NO_RESULTS` is valid only after a successful exact-domain
broker receipt with a verified zero result count. Candidates rejected for source
identity are `SOURCE_IDENTITY_GAP`, not `NO_RESULTS`.

## Security and enforcement boundary

This repository publishes a versioned instruction and validation contract; it
is not a network firewall. `runtime_enforcement=false` remains intentional. A
chatbot host that cannot enforce exact domains, original-host checks, and source
identity must return a gap or `CLOSED_WORLD_VIOLATION`, not claim compliant OA
search.

The deterministic helpers in `reference_consumer/closed_search.py` demonstrate
connector bootstrap validation, route derivation, candidate acceptance, receipt
classification, and fail-closed trace checks. They are optional and do not run
a server.
