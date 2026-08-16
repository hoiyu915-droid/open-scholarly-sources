# Release consistency contract｜發布一致性契約

Open Scholarly Sources distinguishes **build/deployment truth** from **what one external cache happens to return**.

## Three states

1. **Build integrity** — CI generated the registry, profiles, static fallback and release snapshot from one commit and verified their internal contracts.
2. **Deployment status** — GitHub Pages reported the artifact deployment as successful.
3. **Edge observation** — a browser, crawler, proxy or LLM fetcher may still observe an older mutable response for a period of time.

A stale edge observation does not rewrite the identity of the successfully built release.

## Mutable latest endpoints

These are convenient latest-release URLs:

- `/registry.json`
- `/registry.ndjson`
- `/registry.jsonld`
- `/source-profiles.json`
- `/source-profiles.ndjson`
- `/llms.txt`
- `/llms-full.txt`
- `/release-manifest.json`

They track the latest deployed site, but intermediaries may cache an older response. Machine consumers must therefore read the release identity rather than assume that a successful HTTP response is current.

`registry.json`, `source-profiles.json`, the homepage and both LLM text files are stamped with the full release commit SHA. NDJSON remains one source record per line and is paired with the release manifest instead of inserting a metadata line.

## Immutable release endpoints

For each successfully deployed commit `<sha>`:

```text
/releases/<sha>/release-manifest.json
/releases/<sha>/registry.json
/releases/<sha>/registry.ndjson
/releases/<sha>/registry.jsonld
/releases/<sha>/source-profiles.json
/releases/<sha>/source-profiles.ndjson
/releases/<sha>/llms.txt
/releases/<sha>/llms-full.txt
/releases/<sha>/schemas/source.schema.json
/releases/<sha>/schemas/source-profile.schema.json
/releases/<sha>/schemas/release-manifest.schema.json
```

The release manifest records the commit identity, source count, profile-rule version/method and SHA-256 digest/byte size for every immutable file.

A release directory is append-only by identity. If a future deployment tries to reuse an existing commit SHA with different bytes, the archive step fails instead of overwriting the old release.

## Durable history

Pages artifacts are rebuilt from scratch, so old versioned directories would disappear unless they were carried forward. Successfully deployed snapshots are therefore persisted on the dedicated `release-snapshots` branch. A later Pages build imports that archive before adding its new release.

The archive write happens **after** the Pages deployment succeeds. A failed deployment is not promoted into durable release history.

`/releases/index.json` lists the retained releases and the current release ID represented by that deployed site.

## Freshness algorithm for agents

When current-main freshness matters:

1. Fetch `/release-manifest.json` with the machine output you are using.
2. Read `commit_sha` / `release_id`.
3. Query `repository_main_ref_api` from the manifest.
4. If the SHAs match, the fetched release represents current `main` at the time of the comparison.
5. If they differ, treat the mutable response as stale. Fetch `/releases/<main-sha>/release-manifest.json` if that release has already propagated, or retry later/fetch through a different path.
6. For a specific historical release, verify the file SHA-256 against its immutable release manifest.

This contract does not claim that every CDN, crawler or proxy invalidates immediately. It makes staleness **detectable, attributable and reproducible** instead of silently ambiguous.
