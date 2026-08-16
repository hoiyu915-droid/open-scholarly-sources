# Source-use profiles｜來源分級與性格

Open Scholarly Sources keeps **source facts** and **source-use evaluation** separate. Canonical source records describe what a source is, its OA/version semantics, peer-review state, machine endpoints and verification evidence. The profile layer is a deterministic routing heuristic generated from those facts.

本專案把「來源事實」與「來源怎麼用」分開。canonical source record 保存 OA、版本、審查、機器端點與驗證證據；profile 則是由這些事實推導的用途層，不回寫成來源本身的客觀屬性。

## Six routing tiers / 六種用途 tier

- `R1 formal-core / 正式核心` — peer-reviewed formal publication source with a clear version-of-record role.
- `R2 strong-formal / 強正式來源` — formal evidence source with some mixed platform, scope or version caveat.
- `F1 frontier-primary / 前沿主力` — active and verified early-research source suited to frontier discovery.
- `F2 frontier-exploratory / 前沿探索` — useful early signal with higher uncertainty, community scope or partial verification.
- `D1 discovery-infrastructure / 發現基礎設施` — best used to find or connect evidence rather than treated as evidence itself.
- `A1 archive-backbone / 典藏骨架` — repository/archive infrastructure for durable access, backfiles and version recovery.

These tiers are **not a prestige ladder**. `F1` is not below `R1`; they answer different research needs.

這些 tier **不是高低排行榜**。`F1` 並不比 `R1` 低級，而是用途不同：一個追早期訊號，一個承接正式證據。

## Eight 0–4 dimensions / 八個 0–4 軸

- `academic_rigor` — source-level formal review/publication controls / 正式審查與出版控制
- `frontier_velocity` — how early research appears / 前沿速度
- `signal_density` — filtering-density proxy from review status and specialization / 訊號密度代理值
- `machine_readability` — structured formats and verified endpoints / 機器可讀性
- `version_clarity` — separation of preprint, AAM, VOR and review material / 版本清晰度
- `oa_reliability` — consistency of open access within the registered scope / OA 穩定性
- `specialization` — field/community focus / 專門程度
- `noise_risk` — amount of extra filtering needed for early, mixed or unreviewed material / 雜訊警戒

All scores are ordinal heuristics. There is deliberately **no overall score**. In particular, high `noise_risk` means “filter more”, not “bad source”.

所有分數都是序位式啟發值，而且刻意**不計算總分**。尤其 `noise_risk` 高只代表需要更多篩選，不代表來源差。

## Archetypes / 來源性格

Profiles may carry several archetypes at once:

- `formal_anchor` — 正式證據錨點
- `frontier_scout` — 前沿偵察兵
- `specialist_hunter` — 專門領域獵犬
- `broad_firehose` — 廣域消防水管
- `version_bridge` — 版本橋接器
- `archive_backbone` — 典藏骨架
- `methods_workshop` — 方法工作坊
- `heterodox_frontier` — 異端前沿
- `policy_signal` — 政策訊號站
- `clinical_early_warning` — 臨床早期警報
- `discovery_infrastructure` — 發現基礎設施
- `review_observatory` — 審查觀測站
- `community_hub` — 社群前沿樞紐
- `cross_disciplinary_hub` — 跨域樞紐

Some archetypes are fully derived from source fields; a small set of named sources has explicit archetype/tier overrides in `data/source-profile-rules.json`. Overrides are visible and versioned rather than hidden in code.

## Machine outputs / 機器輸出

During Pages deployment, `scripts/build_source_profiles.py` generates:

- `/source-profiles.json`
- `/source-profiles.ndjson`
- `/profiles/` — searchable human-readable profile table

It also embeds `source_profile` into every record in `/registry.json` and `/registry.ndjson`, and appends the profile layer to `llms.txt` and `llms-full.txt`.

The rules are public in `data/source-profile-rules.json`; the output contract is `schemas/source-profile.schema.json`.

## Interpretation boundary / 解讀邊界

A source profile is not an article-level assessment. It does not predict whether a specific paper is correct, reproducible, important or trustworthy. Article-level evidence appraisal still requires study design, methods, data, statistics, replication, conflicts, version history and domain-specific review.
