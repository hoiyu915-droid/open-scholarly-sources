# Contributing sources｜新增來源

The registry is useful only if access claims remain narrower than the evidence. Add sources conservatively.／來源聲稱必須比證據更保守；不確定時就明寫不確定，不要補猜。

## Before adding a source

1. Prefer an official publisher, venue, journal, library, society, government, or repository page as verification evidence.
2. Decide what the entity actually is: journal, journal collection, proceedings series/platform, publisher/review platform, repository, preprint server, aggregator, directory, or digital library.
3. Keep `oa_scope` separate from `access_roles`. A mixed platform can expose full text without every item being OA.
4. Keep `peer_review_scope` separate from `publication_state`. A repository item, OpenReview submission, or preprint must not inherit an accepted journal/conference claim.
5. Add machine endpoints only when the endpoint itself has been verified. `null` is better than a guessed API, feed, or OAI-PMH URL.
6. Record the verification date and primary evidence URL.
7. Use `transition` for announced publisher migrations instead of overwriting the current route early.

## OA scope

- `full` — registered scholarly content is intended to be openly accessible.
- `mixed` — access varies by title, article, year, item, embargo, submission state, or collection state.
- `metadata_only` — discovery/metadata route rather than a canonical full-text host.
- `unknown` — unresolved; do not guess.

For Subscribe-to-Open and similar models, use `mixed` unless the entity and relevant time period are unambiguously open.

## Evidence quality

Good evidence includes an official OA policy, venue or journal page, library publishing page, repository documentation, conference proceedings archive, or government documentation. Search-result snippets and third-party directories may locate evidence but should not be the sole verification record when a primary source exists.

## Canonical data / 核心資料

Start from:

```text
data/registry-manifest.json
```

The manifest lists every canonical source shard. Add the source to the most appropriate existing `data/sources*.json` shard. If a genuinely new subject lane needs its own shard, add the new file to `source_shards` in the manifest.

Every source ID must also have a Traditional Chinese display entry in:

```text
data/i18n.zh-TW.json
```

Each translation contains a `name` and `summary`. Add translations for any new taxonomy values under the relevant taxonomy group as well. English canonical source names and evidence stay in source records; localization is a display/search layer and must not overwrite them.

Do not commit generated copies into `docs/data/`. The Pages workflow copies all canonical JSON files and the schema into the deployment artifact.

Run both validators:

```bash
python3 scripts/validate_registry.py
python3 scripts/validate_extensions.py
```

`validate_extensions.py` enforces manifest integrity, cross-shard unique IDs, parent references, source-type semantics, and exact zh-TW source/taxonomy coverage. A passing validator is necessary but factual claims still need evidence.

## Stable identifiers

Use lowercase kebab-case IDs and do not casually rename an existing ID after publication. Downstream systems may use it as a stable foreign key. If a publisher changes, prefer updating metadata plus `transition` rather than minting a replacement ID for the same entity.
