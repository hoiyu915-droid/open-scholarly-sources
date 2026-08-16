# Open Scholarly Sources｜開放學術來源

A public, versioned registry of scholarly sources useful for open literature discovery and lawful full-text retrieval. 這是一份公開、可版本追蹤的學術來源登錄表，用來支援開放文獻發現、正式出版版本辨識與合法全文取得。

**Browse / 瀏覽：** https://hoiyu915-droid.github.io/open-scholarly-sources/

The project deliberately separates journals, proceedings, publisher and review platforms, institutional and subject repositories, government repositories, preprint servers, directories, aggregators, and digital libraries. A source is not reduced to `OA: true`; access semantics, peer-review scope and publication state stay explicit so downstream crawlers and research agents do not silently turn a mixed platform or preprint into a false open-access/version-of-record claim.

本專案刻意把期刊、會議論文集、出版／審查平台、機構與主題典藏庫、政府典藏庫、預印本、名錄、聚合器及數位文獻庫分開。`OA`、同儕審查、出版狀態是不同欄位，不能互相代替。

## Canonical data / 核心資料

The registry is manifest-driven and split into source shards so subject lanes can grow without turning one JSON file into a monolith. `data/registry-manifest.json` is the entry point and lists every canonical source shard plus the translation layer.

登錄表採 manifest + shard 架構；新增 AI、醫學、植物或其他領域時可以獨立擴充，不必把所有來源塞進同一個巨型 JSON。

- `data/registry-manifest.json` — canonical entry point / 登錄入口
- `data/sources.json` — original multidisciplinary, university, plant, biology and forestry sources
- `data/sources.ai-nlp.json` — ACL/NLP/LLM lane
- `data/sources.ai-ml.json` — ML journals, proceedings and review platforms
- `data/sources.ai-arxiv.json` — arXiv AI/ML/NLP subject projections
- `data/i18n.zh-TW.json` — Traditional Chinese display names, summaries and taxonomy / 繁中顯示層
- `schemas/source.schema.json` — public source-record contract
- `scripts/validate_registry.py` — base-registry validator
- `scripts/validate_extensions.py` — cross-shard, parent-reference and bilingual-coverage validator
- `docs/index.html` — bilingual, searchable GitHub Pages UI

Machine consumers should load `data/registry-manifest.json`, read every file in `source_shards`, and union their `sources` arrays by `id`. The English `name` remains the canonical source name; localized names and summaries are a separate display layer and never overwrite evidence-bearing source records.

機器端應先讀 manifest，再依 `source_shards` 合併各檔的 `sources`。正式英文來源名稱留在 canonical record；繁中只作顯示與搜尋層，不覆蓋來源證據。

## Access semantics / 存取語義

`oa_scope` is intentionally conservative:

| Value | Meaning / 意義 |
| --- | --- |
| `full` | Registered scholarly content is intended to be openly accessible at the source.／登錄內容原則上可公開取得。 |
| `mixed` | Access varies by journal, article, year, item, embargo or platform component.／依刊物、文章、年份或平台元件而異。 |
| `metadata_only` | Useful for discovery/metadata but not itself a canonical full-text host.／可用於發現，但本身不是正式全文主機。 |
| `unknown` | Access status has not been resolved.／尚未判定。 |

`access_roles` separately records `discovery`, `metadata`, `abstract`, `fulltext`, `canonical_vor`, and/or `repository_copy`. Peer review and publication state are separate fields: an open repository is not automatically peer reviewed, and a preprint is never silently upgraded to a version of record.

## AI / LLM source lane｜AI／大型語言模型來源線

The AI expansion treats LLM literature as an ecosystem rather than a single arXiv tag:

- **ACL Anthology** plus venue-level entries for ACL, EMNLP, NAACL, EACL, AACL, CoNLL, Findings, TACL and *Computational Linguistics*
- **OpenReview** as review/publishing infrastructure, with **ICLR** and **TMLR** represented separately so submission/review state is not confused with an accepted publication
- **Proceedings of Machine Learning Research (PMLR)**
- **Journal of Machine Learning Research (JMLR)**
- **NeurIPS Proceedings**
- arXiv projections for **cs.CL**, **cs.LG**, **cs.AI**, **stat.ML**, **cs.CV** and **cs.MA**

The subject taxonomy includes `artificial intelligence`, `machine learning`, `deep learning`, `large language models`, `natural language processing`, `foundation models`, `generative ai`, `multimodal models`, `ai agents`, `alignment and safety`, `evaluation and benchmarking`, `computer vision`, `multi-agent systems` and related terms. The Pages UI indexes both English and Traditional Chinese taxonomy, so searches such as `large language models` / `大型語言模型`, `machine learning` / `機器學習`, or `forestry` / `林業` resolve through the same records.

## Other initial source families / 其他初始來源

The registry also includes:

- Cambridge Core plus Cambridge Forum, Cambridge Materials, Cambridge Prisms and Research Directions
- Columbia University Libraries journals; University of Pennsylvania Press OA/S2O collections; Dartmouth journals; Yale Journal of Biology and Medicine
- Cornell-related routes including Project Euclid, eCommons, Cornell Undergraduate Research Journal and arXiv; Harvard DASH
- forestry/ecology sources including USDA Forest Service Treesearch, Silva Fennica, iForest, Annals of Forest Science, Forest Ecosystems, Trees, Forests and People, and Ecological Solutions and Evidence
- plant/biology sources including BMC Plant Biology, Plant Methods, AoB PLANTS, Horticulture Research, Plant Direct, Applications in Plant Sciences, PhytoKeys and PLOS Biology
- discovery/repository routes including DOAJ, AGRIS, BioOne Complete, bioRxiv Plant Biology, EcoEvoRxiv, USGS Publications Warehouse and Biodiversity Heritage Library

This is a registry, not a ranking. Inclusion is not an endorsement of every article, venue or publisher practice.／這是來源登錄表，不是期刊排名或品質背書。

## Verification rules / 驗證規則

Each source record carries a verification date and evidence URL. Prefer official publisher, venue, library, society, government or repository documentation. Do not infer full OA from a domain name, institution, or the presence of some OA articles.

Time-sensitive states belong in the registry rather than undocumented crawler logic. Publisher migrations can be recorded in a `transition` object while preserving the current canonical route. Review platforms such as OpenReview are classified separately because an openly visible submission or review thread is not automatically an accepted publication.

## Validate locally / 本機驗證

No package installation is required:

```bash
python3 scripts/validate_registry.py
python3 scripts/validate_extensions.py
```

The extension validator checks every manifest shard, cross-shard ID uniqueness, parent references, source enums and URLs, and exact `zh-TW` source/taxonomy coverage. A new source cannot land without its bilingual display entry.

## Contributing / 貢獻

See [CONTRIBUTING.md](CONTRIBUTING.md). New entries should be evidence-backed and conservative about access claims. Add a source to the appropriate shard, register a new shard in the manifest if needed, and add its Traditional Chinese display name and summary. If an endpoint, OA status, publisher relationship or publication state is uncertain, record that uncertainty instead of guessing.

## License

Apache License 2.0. See [LICENSE](LICENSE).
