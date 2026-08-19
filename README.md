# Open Scholarly Sources｜開放學術來源

A public, versioned, bilingual registry of scholarly sources for evidence discovery, lawful full-text retrieval, research-integrity checks and machine-assisted research.

這是一份公開、可版本追蹤、英繁中對照的學術來源登錄表，用來支援文獻發現、正式版本辨識、合法全文取得、預註冊／撤稿查證，以及搜尋引擎與 LLM 的結構化檢索。

**Browse / 瀏覽：** https://hoiyu915-droid.github.io/open-scholarly-sources/

The registry deliberately separates journals, proceedings, review platforms, repositories, preprint servers, trial/preregistration registries, directories, aggregators and digital libraries. It does not collapse access into `OA: true`: OA scope, verified open years, backfile coverage, publication version, licence scope, peer review and publication state are separate claims.

本專案不把「現在可讀」「全刊 OA」「某一年 S2O」「作者接受稿」「正式出版版本」「預印本」「可自由再利用」混成同一件事。

## Current coverage / 目前規模

The current canonical registry contains **244 source entities** across 16 source shards, with **244/244 Traditional Chinese display/search coverage**.

Coverage includes:

- AI, machine learning, NLP, LLMs, proceedings and preprint routes
- multidisciplinary flagships and scholarly-society portfolios
- physics, astronomy, chemistry, Earth/climate and engineering
- biology, genomics, medicine, public health, nutrition and nutritional epidemiology
- mathematics, economics, political science, law, psychology, humanities and social science
- plant science, ecology, forestry, sport/exercise and research data
- preprint and working-paper infrastructure
- trial/preregistration services such as ClinicalTrials.gov, WHO ICTRP, PROSPERO and OSF Registries
- evidence-synthesis and guideline routes such as Cochrane and WHO guideline services
- research-integrity routes such as Retraction Watch data via Crossref
- discovery graphs and OA resolvers such as OpenAlex, CORE, Semantic Scholar, Lens and Unpaywall
- regional/non-English and thesis discovery including Global Index Medicus and NDLTD Taiwan

This is a registry, not a prestige ranking. Inclusion does not endorse every article, editorial decision or publisher practice.

## Canonical data / 核心資料

`data/registry-manifest.json` is the canonical entry point. It lists every source shard and translation shard. Machine consumers can union every `sources` array by stable `id`, then merge the translation shards. English source names remain canonical; Traditional Chinese names and summaries are a display/search layer and never overwrite evidence-bearing source records.

Newer records can carry an `access_policy` object describing OA model, verified effective dates/years, backfile scope, version scope and licence scope. Source-use profiles are generated separately from canonical source facts; see [SOURCE_PROFILES.md](SOURCE_PROFILES.md).

## Default LLM use: source navigation / 預設只做來源導航

**Open Scholarly Sources is a map of where to dig for literature.**

For ordinary requests such as「找這個題目的文獻」「用 OA repo 找來源」「有哪些期刊可以挖」，an LLM should read the pinned registry, select a small number of relevant registered sources, and tell the user where to search and why.

Default behavior is deliberately lightweight:

```text
research topic
→ Open Scholarly Sources registry
→ choose roughly 5 relevant registered sources (maximum 8 by default)
→ point the user to those sources and explain why they are useful
→ stop
```

By default the repo policy does **not** require Crossref, DOAJ, Unpaywall, document-resolution attestations, admissibility judgments or public-ocean fallback. A missing journal-level registry record must not cause ordinary literature discovery to collapse into `discovery_only` results.

See [RETRIEVAL_ROUTING.md](RETRIEVAL_ROUTING.md) and [AGENTS.md](AGENTS.md).

## Chatbot registry-brokered OA search / Chatbot Registry 限定 OA 搜尋

A user can explicitly ask a network-capable chatbot to search a topic using
**only sources selected from this registry**. The published v2 protocol makes
the registry the source-policy authority while a domain-restricted web-search
broker is used only for discovery. Its machine method is
`chatbot_registry_brokered_oa_search_v2`:

```text
topic
→ GitHub connector reads main and pins one immutable release
→ dynamically select active registered sources from that release
→ derive each exact search domain from the selected source's canonical_url
→ domain-restricted broker discovers candidate URLs
→ open the original OA record and verify source identity / evidence scope
→ deduplicate and report results, evidence class and every gap
```

The Pages copies of [`chatbot-entry.txt`](https://hoiyu915-droid.github.io/open-scholarly-sources/chatbot-entry.txt),
[`chatbot-search-protocol.md`](https://hoiyu915-droid.github.io/open-scholarly-sources/chatbot-search-protocol.md)
and [`chatbot-search-routing.json`](https://hoiyu915-droid.github.io/open-scholarly-sources/chatbot-search-routing.json)
are convenient human-readable references. The v2 chatbot bootstrap begins with
the GitHub connector: pin the `main` commit and read the matching
`release-snapshots` files. It does not combine mutable, cached or cross-release
policy files.

The broker's domain filter is a source boundary, not evidence. Search snippets,
rankings, cached text and generated summaries cannot support research claims.
The chatbot must open the original result on the exact canonical hostname,
verify the registered container/repository identity, and reject ambiguous
results on shared publisher hosts. A `metadata_only` source stays metadata-only;
it cannot be upgraded to full-text evidence. Returned DOI, publisher and
download links do not authorize a new host.

The published direct topic-search adapters remain an optional secondary route.
`registry_closed` and `direct_only` preserve the strict adapter-only behavior;
missing adapters remain `NO_SEARCH_ADAPTER` there. In brokered mode, preserve
`NO_CANONICAL_SEARCH_ROUTE`, `SEARCH_BROKER_GAP`, `SOURCE_IDENTITY_GAP`,
`ORIGINAL_FETCH_GAP`, `FULLTEXT_NOT_AUTHORIZED`, `REGISTRY_COVERAGE_GAP` and
`CLOSED_WORLD_VIOLATION` rather than silently substituting unrestricted search
or public-ocean fallback.

No Skill, MCP, custom server, Radar integration or API credential is required.
This is an auditable chatbot contract, not a firewall: the host must follow the
pinned release, exact domain/path checks and truthful trace
(`runtime_enforcement=false`).

## Verification is optional and user-activated / 認證按需啟動

The stricter resolution/admissibility route remains available, but it is **off by default** and must not be self-activated by an LLM.

It starts only after an explicit request such as「核實這些文獻」「驗證來源」「啟動認證路由」「做 source audit」。When enabled, the registry-first monotonic safety rule still applies:

> Uncertainty may widen the verification search, but may never upgrade evidence or close a required lane.

The reference verification entry point is:

```bash
python3 scripts/validate_routing_policy.py
python3 -m unittest -v tests.test_reference_consumer
python3 reference_consumer/verify.py --input examples/reference-consumer-formal-evidence.json
```

`reference_consumer/route.py` contains lower-level resolver/gate primitives; it is not the default literature-discovery workflow.

The repository publishes the contract and reference implementation, but does **not** enforce arbitrary external agent runtimes (`runtime_enforcement=false`).

## Machine outputs / 機器輸出

Every Pages deployment generates:

- `/registry.json` — consolidated bilingual registry
- `/registry.ndjson` — one source record per line
- `/registry.jsonld` — Schema.org catalog
- `/source-profiles.json` and `/source-profiles.ndjson`
- `/retrieval-routing-policy.json` — versioned source-navigation / optional-verification contract
- `/chatbot-entry.txt` — smallest bootstrap prompt for registry-brokered OA search
- `/chatbot-search-routing.json` — versioned registry-derived broker/direct routing contract
- `/chatbot-search-protocol.md` — complete no-Skill/no-server/Radar chatbot procedure
- `/llms.txt` and `/llms-full.txt`
- `/sources/<id>.html` and `/sources/index.html`
- `/profiles/`
- `/sitemap.xml` and `/robots.txt`

These files improve conventional crawling, retrieval and machine parsing, but they do **not** guarantee ingestion by any particular search engine or LLM provider.

## Release identity and cache consistency / 發布識別與快取一致性

Mutable Pages URLs such as `/registry.json`, `/retrieval-routing-policy.json` and `/llms.txt` are convenience endpoints for the latest deployed release. Intermediary caches or propagation can temporarily return an older release, so a single external fetch is not sufficient proof of the current repository state.

Every deployment therefore stamps the public machine outputs with a full Git commit identity and creates:

- `/release-manifest.json` — mutable manifest for the release returned by that endpoint
- `/releases/<full-commit-sha>/...` — immutable machine snapshot
- `/releases/<full-commit-sha>/release-manifest.json` — SHA-256 digests and release metadata
- `/releases/<full-commit-sha>/retrieval-routing-policy.json` — immutable routing policy used by that release
- `/releases/<full-commit-sha>/chatbot-entry.txt`
- `/releases/<full-commit-sha>/chatbot-search-routing.json`
- `/releases/<full-commit-sha>/chatbot-search-protocol.md`
- `/releases/<full-commit-sha>/schemas/retrieval-routing-policy.schema.json`
- `/releases/index.json` — release history/pointers retained from deployed releases

The release manifest records routing-policy identity and chatbot-search protocol/method/schema/adapter count in addition to profile-rule identity. The chatbot's GitHub connector bootstrap uses the `main` ref and the matching immutable snapshot under the dedicated `release-snapshots` branch; snapshots are persisted **only after the Pages deployment succeeds**. Reusing an existing release SHA with different bytes is a release failure.

The repository copy of `docs/index.html` is only a build template; each immutable release preserves the exact rendered homepage and generated static source index for independent crawler-facing verification.

New immutable releases are self-contained historical mini-sites: open `/releases/<sha>/` to browse the rendered homepage, its local data dependencies, source pages and profiles without falling back to mutable root paths.

When freshness matters, compare `commit_sha` from the fetched release manifest with the repository `main` ref. If they differ, the fetched mutable endpoint is stale; use the commit-addressed immutable snapshot or retry through a fresh path. See [RELEASE_CONSISTENCY.md](RELEASE_CONSISTENCY.md).

## Validate and build locally / 本機驗證與建置

No third-party Python package is required for the core build:

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

CI additionally builds a commit-addressed release snapshot, verifies its SHA-256 digests, checks routing-policy identity, checks the no-JavaScript homepage fallback and ensures release finalization is idempotent for the same commit SHA.

## Contributing / 貢獻

See [CONTRIBUTING.md](CONTRIBUTING.md). Add evidence-backed claims only. `null`, `unknown` and `mixed` are preferable to a convincing-looking guess.

## License

Apache License 2.0. See [LICENSE](LICENSE).
