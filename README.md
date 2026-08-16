# Open Scholarly Sources｜開放學術來源

A public, versioned, bilingual registry of scholarly sources useful for open-literature discovery, lawful full-text retrieval and machine-assisted research.

這是一份公開、可版本追蹤、英繁中對照的學術來源登錄表，用來支援開放文獻發現、正式版本辨識、合法全文取得，以及搜尋引擎與 LLM 的結構化檢索。

**Browse / 瀏覽：** https://hoiyu915-droid.github.io/open-scholarly-sources/

The registry deliberately separates journals, proceedings, publisher/review platforms, repositories, preprint servers, directories, aggregators and digital libraries. It does not collapse access into `OA: true`: OA scope, verified open years, backfile coverage, publication version, licence scope, peer review and publication state are separate claims.

本專案不把「現在可讀」「全刊 OA」「某一年 S2O」「作者接受稿」「正式出版版本」「可自由再利用」混成同一件事。

## Current coverage / 目前規模

The current registry contains **115 source entities** across:

- AI, machine learning, NLP and LLM publication routes
- multidisciplinary flagships and scholarly-society portfolios
- physics, astronomy, high-energy physics and chemistry
- Earth system, atmosphere, climate, hydrology and geoscience
- biology, genomics, molecular medicine, clinical medicine and public health
- mathematics, economics, demography, cognitive science, law and humanities
- plant science, ecology and forestry
- repositories, directories, aggregators and historical digital libraries

This is a registry, not a ranking. Inclusion does not endorse every article, editorial decision or publisher practice.

## Canonical data / 核心資料

`data/registry-manifest.json` is the canonical entry point. It lists every source shard and translation shard.

```text
data/
├── registry-manifest.json
├── sources.json
├── sources.ai-nlp.json
├── sources.ai-ml.json
├── sources.ai-arxiv.json
├── sources.cross-disciplinary.json
├── sources.physical-earth.json
├── sources.life-health.json
├── sources.social-humanities.json
├── i18n.zh-TW.json
└── i18n.zh-TW.cross-disciplinary.json
```

Machine consumers should read the manifest, union every `sources` array by stable `id`, then merge every translation shard. English names remain canonical; Traditional Chinese names and summaries are a display/search layer and never overwrite evidence-bearing source records.

## Access semantics / 存取語義

`oa_scope` remains conservative:

| Value | Meaning / 意義 |
| --- | --- |
| `full` | Registered content is intended to be openly accessible; licence and version may still vary.／登錄內容可公開取得，但授權與版本可能不同。 |
| `mixed` | Access varies by journal, article, year, item, embargo or platform component.／依刊物、文章、年份或平台元件而異。 |
| `metadata_only` | Discovery/metadata route, not a canonical full-text host.／發現與中繼資料來源，本身不是全文主機。 |
| `unknown` | Not yet resolved.／尚未判定。 |

Newer records can also carry an `access_policy` object:

- `model` — gold, diamond, Subscribe to Open, repository, consortium-funded, platform transition, etc.
- `effective_from` — verified effective date or year
- `open_years` — only years confirmed open; especially important for S2O
- `backfile_scope` — full, mixed, partial, unknown or not applicable
- `version_scope` — version of record, accepted manuscript, preprint, review material, etc.
- `license_scope` — uniform CC BY, another uniform open licence, mixed or unknown

A source can be free to read without granting uniform reuse rights. A repository may contain VORs, accepted manuscripts and preprints together. These distinctions are release data, not hidden crawler assumptions.

## LLM and search discoverability / LLM 與搜尋索引

Every Pages deployment generates the following from the same canonical manifest:

- `/registry.json` — consolidated bilingual registry
- `/registry.ndjson` — one complete source record per line
- `/registry.jsonld` — Schema.org `DataCatalog` / `Dataset`
- `/llms.txt` — concise machine discovery guide
- `/llms-full.txt` — complete bilingual text representation
- `/sources/<id>.html` — stable static page for every source
- `/sources/index.html` — static source directory
- `/sitemap.xml` and `/robots.txt`

These files materially improve conventional crawling, retrieval and machine parsing, but they do **not** guarantee ingestion by any particular search engine or LLM provider.

## Source families / 主要來源群

The registry now includes, among others:

- Royal Society Publishing, ACM Digital Library, Royal Astronomical Society journals, Copernicus Publications and SCOAP³
- Nature Communications, PNAS Nexus, Science Advances, Physical Review X, SciPost Physics, ACS Central Science and Chemical Science
- PubMed Central, Europe PMC, NAR Journals, JAMA Network Open and PLOS Medicine
- Forum of Mathematics Pi/Sigma, Theoretical Economics, Demography, Open Mind and Journal of Legal Analysis
- Open Library of Humanities
- ACL Anthology, OpenReview, ICLR, TMLR, PMLR, JMLR, NeurIPS Proceedings and arXiv AI/ML/NLP projections
- the original university, plant, biology, ecology and forestry sources

## Validate and build locally / 本機驗證與建置

No third-party Python package is required:

```bash
python3 scripts/validate_registry.py
python3 scripts/validate_extensions.py
rm -rf /tmp/open-scholarly-sources-site
python3 scripts/build_machine_index.py --output /tmp/open-scholarly-sources-site
```

CI checks the original base registry, every manifest shard, cross-shard ID uniqueness, parent references, access-policy semantics, exact zh-TW coverage and the complete machine-index build.

## Contributing / 貢獻

See [CONTRIBUTING.md](CONTRIBUTING.md). Add evidence-backed claims only. `null`, `unknown` and `mixed` are preferable to a convincing-looking guess.

## License

Apache License 2.0. See [LICENSE](LICENSE).
