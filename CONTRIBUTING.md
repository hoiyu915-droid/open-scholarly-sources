# Contributing sources｜新增來源規則

The registry is useful only when its claims remain narrower than the evidence. 嘴可以大，證據不能膨風。

## Before adding a source / 新增前

1. Use an official publisher, journal, scholarly society, library, government or repository page as primary evidence.
2. Identify the entity correctly: journal, journal collection, publisher platform, proceedings platform, review platform, repository, preprint server, aggregator, directory or digital library.
3. Keep OA scope, peer review, publication state, document version and reuse licence separate.
4. Add only verified machine endpoints. Use `null` rather than guessing an API, RSS or OAI-PMH URL.
5. Record an ISO verification date and evidence URL.
6. Reuse stable lowercase kebab-case IDs; do not casually rename IDs already released.

## Choose the correct shard / 選擇資料 shard

Edit the subject-appropriate source file listed in `data/registry-manifest.json`. Create a new shard only when a subject lane is large enough to maintain independently, then add it to `source_shards`.

Every source also needs a `zh-TW` name and summary. Add these to the relevant file in `translation_shards`. Translation shards are merged at build time; duplicate source IDs are rejected.

## OA scope / OA 範圍

- `full` — registered content is intended to be openly accessible.
- `mixed` — access varies by title, article, year, item, embargo or component.
- `metadata_only` — discovery/metadata route, not a hosted full-text source.
- `unknown` — unresolved.

Do not mark an entire platform `full` merely because it contains some OA journals or articles.

## Temporal and version semantics / 年份與版本語義

Use `access_policy` when access depends on a model, date, year, backfile or document version:

```json
{
  "access_policy": {
    "model": "subscribe_to_open",
    "effective_from": null,
    "open_years": ["2026"],
    "backfile_scope": "mixed",
    "version_scope": ["version_of_record"],
    "license_scope": "mixed",
    "notes": "Only the verified 2026 volume is OA; do not project this status forward."
  }
}
```

Rules:

- Subscribe to Open entries must list at least one verified `open_year`.
- An open year is not a promise about the next year.
- `free to read` does not imply CC BY or other reusable licensing.
- Repositories that mix VORs, accepted manuscripts and preprints must say so in `version_scope`.
- If a journal migrated publishers, use `transition` rather than silently rewriting history.
- Closed or merged historical routes should remain `status: inactive` when they are still needed for archive discovery.

## Translation taxonomy / 翻譯分類

New subject labels and access-policy values need zh-TW taxonomy entries. CI merges all translation shards and requires exact coverage for:

- subjects and source types
- OA, review and publication states
- access roles and verification states
- OA models, backfile scopes, version scopes and licence scopes

## Validate and build / 驗證與建置

### Registry-brokered chatbot search

The default explicit chatbot search contract is the generic
`chatbot_registry_brokered_oa_search_v2` route. It must work from the pinned
registry rather than from a hard-coded list of source IDs. For every selected
source, derive the route from its canonical record:

- require `status=active`, a `discovery` access role, and a safe HTTPS
  `canonical_url` with an exact hostname; reject userinfo, fragments, explicit
  ports, wildcard expansion and unsafe schemes;
- use that exact canonical hostname as the web-search domain restriction and
  as the permitted original-fetch host; a canonical path is an identity hint,
  not permission to invent a broader path rule;
- treat snippets, rankings, cached text and generated summaries as discovery
  data only; the original OA record must be opened before content claims are
  accepted;
- verify the original container/repository identity using the registered name
  and any available title, ISSN, repository ID, DOI or source-prefix evidence;
  a shared publisher hostname alone is insufficient;
- keep `metadata_only` records at metadata scope. They may discover records but
  cannot provide full-text evidence;
- never follow a returned DOI, publisher or download URL to an unregistered
  host. Record `SOURCE_IDENTITY_GAP`, `ORIGINAL_FETCH_GAP` or
  `FULLTEXT_NOT_AUTHORIZED` when the boundary cannot be proven.

This route uses no Skill, MCP, custom server, Radar integration or API
credential. The external web-search service is a discovery broker, not an
evidence source.

### Direct chatbot search adapters

Add an adapter only when the endpoint supports real topic search and has a live
receipt. A feed, OAI-PMH harvest endpoint, bulk dump, DOI resolver or merely
non-null `machine_access` field is not automatically a topic-search adapter.

Direct adapters are optional secondary routes in brokered v2 and remain the
strict route for `registry_closed` / `direct_only` requests. Do not make the
brokered route depend on a fixed adapter list.

Every searchable adapter in `data/chatbot-search-routing.json` must:

- refer to an active registered source and a declared `machine_access` base;
- use unauthenticated HTTPS GET in protocol v1;
- expose only `{query}` and `{limit}` substitutions;
- declare exact lowercase hosts, never wildcards;
- keep redirects on the same declared host;
- declare accepted Content-Types, parser, bounded result limits, OA guard and dedupe keys;
- store a dated live HTTP/Content-Type receipt and primary evidence URL.

If an endpoint needs a key, POST body, browser session or unregistered redirect,
do not mark it searchable in the server-free v1 contract. Preserve the gap.

### Commands

Run the complete validation set:

```bash
python3 scripts/validate_registry.py
python3 scripts/validate_extensions.py
python3 scripts/validate_routing_policy.py
python3 scripts/validate_chatbot_search.py
python3 -m unittest -v tests.test_reference_consumer tests.test_chatbot_search
rm -rf /tmp/open-scholarly-sources-site
mkdir -p /tmp/open-scholarly-sources-site/data /tmp/open-scholarly-sources-site/schemas
cp docs/index.html /tmp/open-scholarly-sources-site/index.html
cp data/*.json /tmp/open-scholarly-sources-site/data/
cp schemas/*.json /tmp/open-scholarly-sources-site/schemas/
python3 scripts/build_machine_index.py --output /tmp/open-scholarly-sources-site
python3 scripts/build_source_profiles.py --output /tmp/open-scholarly-sources-site
python3 scripts/build_static_homepage.py --site /tmp/open-scholarly-sources-site
python3 scripts/publish_routing_policy.py --output /tmp/open-scholarly-sources-site
python3 scripts/publish_chatbot_search.py --output /tmp/open-scholarly-sources-site
```

Do not commit generated copies of `registry.json`, `llms.txt`, per-source HTML or files under `docs/data/`. The Pages workflow regenerates them from canonical data. Only `docs/index.html` is maintained directly.

A passing validator proves structural consistency, not factual truth. Review the evidence before merging.
