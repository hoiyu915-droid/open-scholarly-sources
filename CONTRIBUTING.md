# Contributing sources

The registry is useful only if access claims remain narrower than the evidence. Add sources conservatively.

## Before adding a source

1. Prefer an official publisher, journal, library, society, government, or repository page as verification evidence.
2. Decide what the entity actually is: a journal, collection, publisher platform, repository, preprint server, aggregator, directory, or digital library.
3. Keep `oa_scope` separate from `access_roles`. A mixed platform can offer full text without every item being OA.
4. Keep `peer_review_scope` separate from `publication_state`. Repositories and preprint servers must not inherit journal-level peer-review claims.
5. Add machine endpoints only when the endpoint itself has been verified. `null` is better than a guessed API, feed, or OAI-PMH URL.
6. Record the verification date and evidence URL.
7. Use `transition` when a journal/platform has an announced publisher migration instead of overwriting the present route early.

## OA scope

- `full` — the registered source is intended to make its scholarly content openly accessible.
- `mixed` — access varies by title, article, year, item, embargo, or collection state.
- `metadata_only` — the source is a discovery/metadata route rather than a full-text host.
- `unknown` — unresolved; do not guess.

For Subscribe-to-Open and similar models, use `mixed` unless the registry entity and time period are unambiguously open.

## Evidence quality

Good evidence includes an official OA policy, journal about page, library publishing page, repository documentation, or government service documentation. Search-result snippets and third-party directories can help locate evidence but should not be the only verification record when a primary source exists.

## Data changes

Edit only the canonical file:

```text
data/sources.json
```

Do not commit generated copies into `docs/data/`. The Pages workflow stages the canonical JSON and schema into the deployment artifact.

Then run:

```bash
python3 scripts/validate_registry.py
```

A passing validator is necessary but not sufficient: factual source claims still need evidence.

## Stable identifiers

Use lowercase kebab-case IDs and do not casually rename an existing ID after publication. Downstream systems may use it as a stable foreign key. If a publisher changes, prefer updating the source metadata and recording a transition rather than minting a replacement ID for the same journal.
