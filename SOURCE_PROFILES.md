# Source-use profiles｜來源分級與性格

Open Scholarly Sources keeps **source facts** and **source-use evaluation** separate. Canonical source records describe what a source is, its OA/version semantics, peer-review state, machine endpoints and verification evidence. The profile layer is a deterministic routing heuristic generated from those facts.

本專案把「來源事實」與「來源怎麼用」分開。canonical source record 保存 OA、版本、審查、機器端點與驗證證據；profile 則是由這些事實推導的用途層，不回寫成來源本身的客觀屬性。

## Six routing tiers / 六種用途 tier

- `R1 formal-core / 正式核心` — peer-reviewed formal publication source with a clear version-of-record role.
- `R2 strong-formal / 強正式來源` — formal or openly reviewed evidence source with some state, scope or version caveat.
- `F1 frontier-primary / 前沿主力` — active and verified early-research source suited to frontier discovery.
- `F2 frontier-exploratory / 前沿探索` — useful early signal with higher uncertainty, community scope, partial verification, or inactive submission status.
- `D1 discovery-infrastructure / 發現／查證基礎設施` — discovery, registration, integrity checking, scholarly graphs, guideline lookup and review-observation routes.
- `A1 archive-backbone / 典藏骨架` — repositories for durable access, backfiles, datasets, theses and version recovery.

These tiers are **not a prestige ladder**. `F1` is not below `R1`; a trial registry or retraction service is not “low quality” because it is `D1`.

## Eight 0–4 dimensions / 八個 0–4 軸

- `academic_rigor` — source-level formal review/publication controls / 正式審查與出版控制
- `frontier_velocity` — how early research appears / 前沿速度
- `signal_density` — filtering-density proxy from review status and specialization / 訊號密度代理值
- `machine_readability` — structured formats and verified endpoints / 機器可讀性
- `version_clarity` — separation of preprint, AAM, VOR, registration and review material / 版本清晰度
- `oa_reliability` — consistency of open access within the registered scope / OA 穩定性
- `specialization` — field/community focus / 專門程度
- `noise_risk` — amount of extra filtering needed for early, mixed or unreviewed material / 雜訊警戒

All scores are ordinal heuristics. There is deliberately **no overall score**.

## Provenance / 評分可追溯性

Every generated profile now carries:

- `rule_version` and a public `rules_url`
- the canonical source fields used to derive the profile
- the source's verification status, checked date and evidence URL
- the automatic tier/archetypes before overrides
- whether an explicit override was applied, plus the override itself

This means a reviewer can trace `source -> verified facts -> deterministic rules -> automatic result -> explicit override -> final profile`. The profile is no longer an unexplained assertion.

## Archetypes / 來源性格

A source may carry several archetypes at once. Important ones include:

- `formal_anchor` — 正式證據錨點
- `frontier_scout` — 前沿偵察兵
- `specialist_hunter` — 專門領域獵犬
- `broad_firehose` — **高流量廣域來源**；資料量很大、領域很廣，若不篩選容易被大量訊號淹沒
- `version_bridge` — 版本橋接器
- `evidence_synthesis_anchor` — 實證綜整錨點
- `guideline_authority` — 指引權威來源
- `research_integrity_watch` — 研究誠信警戒站
- `preregistration_registry` — 預註冊查證庫
- `trial_registry` — 臨床試驗註冊庫
- `publish_review_curate` — 先發表－再審查－再策展
- `open_peer_review` — 公開同儕審查
- `overlay_peer_review` — 疊加式預印本審查
- `scholarly_graph` — 學術關聯圖譜
- `oa_resolver` — 合法 OA 版本定位器
- `regional_discovery` — 區域／非英語文獻入口
- `thesis_archive` — 學位論文典藏
- `data_repository` — 研究資料典藏
- `historical_preprint_archive` — 歷史預印本典藏

`broad_firehose` 不再直譯成「消防水管」；中文採用途語義「高流量廣域來源」。

## Machine outputs / 機器輸出

Pages deployment generates:

- `/registry.json` and `/registry.ndjson`, each source embedding its `source_profile`
- `/source-profiles.json`
- `/source-profiles.ndjson`
- `/profiles/`
- `llms.txt` and `llms-full.txt` with profile routing information
- a deploy-time static fallback source table inside `/index.html`

The homepage still offers interactive filters, but the generated HTML now also contains a compact source table so crawlers, text-only clients and agents that do not execute JavaScript do not see an empty shell.

## Interpretation boundary / 解讀邊界

A source profile is not an article-level assessment. It does not predict whether a specific paper is correct, reproducible, important or trustworthy. Article-level evidence appraisal still requires study design, methods, data, statistics, replication, conflicts, registration history, outcome changes, corrections/retractions and domain-specific review.
