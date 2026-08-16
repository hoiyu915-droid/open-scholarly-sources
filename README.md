# Open Scholarly Sources｜開放學術來源

A public, versioned, bilingual registry of scholarly sources for evidence discovery, lawful full-text retrieval, research-integrity checks and machine-assisted research.

這是一份公開、可版本追蹤、英繁中對照的學術來源登錄表，用來支援文獻發現、正式版本辨識、合法全文取得、預註冊／撤稿查證，以及搜尋引擎與 LLM 的結構化檢索。

**Browse / 瀏覽：** https://hoiyu915-droid.github.io/open-scholarly-sources/

The registry deliberately separates journals, proceedings, review platforms, repositories, preprint servers, trial/preregistration registries, directories, aggregators and digital libraries. It does not collapse access into `OA: true`: OA scope, verified open years, backfile coverage, publication version, licence scope, peer review and publication state are separate claims.

本專案不把「現在可讀」「全刊 OA」「某一年 S2O」「作者接受稿」「正式出版版本」「預印本」「可自由再利用」混成同一件事。

## Current coverage / 目前規模

The current canonical registry contains **227 source entities** across 14 source shards, with **227/227 Traditional Chinese display/search coverage**.

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

## Machine outputs / 機器輸出

Every Pages deployment generates:

- `/registry.json` — consolidated bilingual registry
- `/registry.ndjson` — one source record per line
- `/registry.jsonld` — Schema.org catalog
- `/source-profiles.json` and `/source-profiles.ndjson`
- `/llms.txt` and `/llms-full.txt`
- `/sources/<id>.html` and `/sources/index.html`
- `/profiles/`
- `/sitemap.xml` and `/robots.txt`

These files improve conventional crawling, retrieval and machine parsing, but they do **not** guarantee ingestion by any particular search engine or LLM provider.

## Release identity and cache consistency / 發布識別與快取一致性

Mutable Pages URLs such as `/registry.json` and `/llms.txt` are convenience endpoints for the latest deployed release. Intermediary caches or propagation can temporarily return an older release, so a single external fetch is not sufficient proof of the current repository state.

Every deployment therefore stamps the public machine outputs with a full Git commit identity and creates:

- `/release-manifest.json` — mutable manifest for the release returned by that endpoint
- `/releases/<full-commit-sha>/...` — immutable machine snapshot
- `/releases/<full-commit-sha>/release-manifest.json` — SHA-256 digests and release metadata
- `/releases/index.json` — release history/pointers retained from deployed releases

The immutable snapshots are persisted on the dedicated `release-snapshots` branch **only after the Pages deployment succeeds**. Reusing an existing release SHA with different bytes is a release failure.

When freshness matters, compare `commit_sha` from the fetched release manifest with the repository `main` ref. If they differ, the fetched mutable endpoint is stale; use the commit-addressed immutable snapshot or retry through a fresh path. See [RELEASE_CONSISTENCY.md](RELEASE_CONSISTENCY.md).

## Validate and build locally / 本機驗證與建置

No third-party Python package is required for the core build:

```bash
python3 scripts/validate_registry.py
python3 scripts/validate_extensions.py
rm -rf /tmp/open-scholarly-sources-site
mkdir -p /tmp/open-scholarly-sources-site/data /tmp/open-scholarly-sources-site/schemas
cp docs/index.html /tmp/open-scholarly-sources-site/index.html
cp data/*.json /tmp/open-scholarly-sources-site/data/
cp schemas/*.json /tmp/open-scholarly-sources-site/schemas/
python3 scripts/build_machine_index.py --output /tmp/open-scholarly-sources-site
python3 scripts/build_source_profiles.py --output /tmp/open-scholarly-sources-site
python3 scripts/build_static_homepage.py --site /tmp/open-scholarly-sources-site
```

CI additionally builds a commit-addressed release snapshot, verifies its SHA-256 digests, checks the no-JavaScript homepage fallback and ensures release finalization is idempotent for the same commit SHA.

## Contributing / 貢獻

See [CONTRIBUTING.md](CONTRIBUTING.md). Add evidence-backed claims only. `null`, `unknown` and `mixed` are preferable to a convincing-looking guess.

## License

Apache License 2.0. See [LICENSE](LICENSE).
