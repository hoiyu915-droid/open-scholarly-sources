# Open Scholarly Sources

A public, versioned registry of scholarly sources that are useful for open literature discovery and lawful full-text retrieval.

**Browse the registry:** https://hoiyu915-droid.github.io/open-scholarly-sources/

The project deliberately separates journals, journal families, publisher platforms, institutional and subject repositories, government repositories, preprint servers, directories, aggregators, and digital libraries. A source is not marked simply `OA: true`; access semantics are explicit so downstream crawlers and research agents do not turn a mixed platform into a false open-access claim.

## Canonical data

`data/sources.json` is the single source of truth. The GitHub Pages site is a generated view of that file.

- `data/sources.json` — canonical registry
- `schemas/source.schema.json` — public data contract
- `scripts/validate_registry.py` — dependency-free structural and semantic validator
- `docs/index.html` — human-readable registry UI
- `.github/workflows/validate.yml` — validation on branches and pull requests
- `.github/workflows/pages.yml` — validation and Pages deployment from `main`

Machine consumers can use the repository file directly after release on `main`:

```text
https://raw.githubusercontent.com/hoiyu915-droid/open-scholarly-sources/main/data/sources.json
```

## Access semantics

`oa_scope` is intentionally conservative:

| Value | Meaning |
| --- | --- |
| `full` | Registered scholarly content is intended to be openly accessible at the source. |
| `mixed` | Access varies by journal, article, year, item, embargo, or platform component. Verify at the record level. |
| `metadata_only` | Useful for discovery/metadata, but not itself a canonical full-text host. |
| `unknown` | Access status has not yet been resolved. |

`access_roles` separately records what a source can contribute: `discovery`, `metadata`, `abstract`, `fulltext`, `canonical_vor`, and/or `repository_copy`.

Peer review and publication state are separate fields. An open repository is not automatically peer reviewed; a preprint is not silently upgraded to a version of record.

## Initial source families

The seed registry includes sources already reviewed for this project, including:

- Cambridge Core plus Cambridge Forum, Cambridge Materials, Cambridge Prisms, and Research Directions
- Columbia University Libraries journal platform
- University of Pennsylvania Press Diamond/Platinum OA and Subscribe-to-Open collections
- Dartmouth Digital Publishing journals and Yale Journal of Biology and Medicine
- Cornell-related routes including Project Euclid, eCommons, Cornell Undergraduate Research Journal, and arXiv
- Harvard DASH
- forestry and ecology sources including USDA Forest Service Treesearch, Silva Fennica, iForest, Annals of Forest Science, Forest Ecosystems, Trees, Forests and People, and Ecological Solutions and Evidence
- plant and biology journals including BMC Plant Biology, Plant Methods, AoB PLANTS, Horticulture Research, Plant Direct, Applications in Plant Sciences, PhytoKeys, and PLOS Biology
- discovery and repository routes including DOAJ, AGRIS, BioOne Complete, bioRxiv Plant Biology, EcoEvoRxiv, USGS Publications Warehouse, and Biodiversity Heritage Library

This is a registry, not a ranking. Inclusion is not an endorsement of every article or publisher practice.

## Verification rules

Each source record carries a verification date and evidence URL. Prefer official publisher, journal, library, society, government, or repository documentation. Do not infer full OA from a domain name, an institution, or the presence of some OA articles.

Time-sensitive states belong in the registry rather than in undocumented crawler logic. For example, publisher migrations can be recorded in a `transition` object while preserving the current canonical route.

## Validate locally

No package installation is required:

```bash
python3 scripts/validate_registry.py
```

The validator checks IDs, enums, URLs, dates, parent references, machine-access fields, metadata-only constraints, preprint/VOR conflicts, and the schema JSON itself.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). New entries should be evidence-backed and conservative about access claims. If an endpoint, OA status, publisher, or platform relationship is uncertain, record that uncertainty instead of guessing.

## License

Apache License 2.0. See [LICENSE](LICENSE).
