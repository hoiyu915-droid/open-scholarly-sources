# Release consistency contract｜發布一致性契約

Open Scholarly Sources distinguishes **build/deployment truth** from **what one external cache happens to return**.

## Three states

1. **Build integrity** — CI generated the registry, profiles, routing policy, static fallback and release snapshot from one commit and verified their internal contracts.
2. **Deployment status** — GitHub Pages reported the artifact deployment as successful.
3. **Edge observation** — a browser, crawler, proxy or LLM fetcher may still observe an older mutable response for a period of time.

A stale edge observation does not rewrite the identity of the successfully built release.

## Template versus deployed HTML

`docs/index.html` in the Git repository is intentionally a **build template**. It contains the `STATIC_FALLBACK` insertion marker and the JavaScript table shell, so inspecting that template alone does not prove or disprove what Pages serves.

During CI/Pages build, `scripts/build_static_homepage.py` replaces the marker with one static HTML row per registered source. The release finalizer then stamps the release identity. The exact rendered result is preserved as `/releases/<sha>/rendered-homepage.html`, while the generated static source directory is preserved as `/releases/<sha>/rendered-source-index.html`. Their SHA-256 digests are recorded in that release's manifest.

Release validation fails unless the rendered homepage contains the static fallback heading and exactly one `./sources/<id>.html` link for every registered source.

## Mutable latest endpoints

These are convenient latest-release URLs:

- `/registry.json`
- `/registry.ndjson`
- `/registry.jsonld`
- `/source-profiles.json`
- `/source-profiles.ndjson`
- `/retrieval-routing-policy.json`
- `/chatbot-search-routing.json`
- `/chatbot-search-protocol.md`
- `/chatbot-entry.txt`
- `/llms.txt`
- `/llms-full.txt`
- `/release-manifest.json`

They track the latest deployed site, but intermediaries may cache an older response. Machine consumers must therefore read the release identity rather than assume that a successful HTTP response is current.

`registry.json`, `source-profiles.json`, the homepage and both LLM text files are stamped with the full release commit SHA. NDJSON remains one source record per line and is paired with the release manifest instead of inserting a metadata line. The routing-policy and chatbot-search files carry their own version/method identity; their immutable digests are recorded by the same release manifest.

## Immutable release endpoints

For each successfully deployed commit `<sha>` after routing-policy activation:

```text
/releases/<sha>/release-manifest.json
/releases/<sha>/registry.json
/releases/<sha>/registry.ndjson
/releases/<sha>/registry.jsonld
/releases/<sha>/source-profiles.json
/releases/<sha>/source-profiles.ndjson
/releases/<sha>/retrieval-routing-policy.json
/releases/<sha>/chatbot-search-routing.json
/releases/<sha>/chatbot-search-protocol.md
/releases/<sha>/chatbot-entry.txt
/releases/<sha>/llms.txt
/releases/<sha>/llms-full.txt
/releases/<sha>/schemas/source.schema.json
/releases/<sha>/schemas/source-profile.schema.json
/releases/<sha>/schemas/retrieval-routing-policy.schema.json
/releases/<sha>/schemas/chatbot-search-routing.schema.json
/releases/<sha>/schemas/release-manifest.schema.json
```

Earlier Pages deployments remain recoverable from Git history and retained Actions artifacts where available, but they are not promised to contain routing-policy files retroactively.

The release manifest records the commit identity, source count, profile-rule identity, routing-policy identity, chatbot-search protocol/method/schema/adapter count, and SHA-256 digest/byte size for every immutable file.

The release-manifest schema is `3.0.0` for releases carrying required chatbot-search identity. This is an intentional breaking schema bump from `2.0.0`: the new identity fields are required, so the repository does not pretend the contract is backward-compatible merely because they are additive in JSON syntax.

A release directory is append-only by identity. If a future deployment tries to reuse an existing commit SHA with different bytes, the archive step fails instead of overwriting the old release.

## Routing-policy identity

A consumer claiming compliance with the retrieval-routing contract should bind all of the following to the trace:

```text
registry release_id / commit_sha
routing_policy_version
routing_policy_method
routing_policy_schema_version
SHA-256 of retrieval-routing-policy.json
chatbot_search_protocol_version
chatbot_search_method
chatbot_search_schema_version
chatbot_search_adapter_count
SHA-256 of chatbot-search-routing.json and chatbot-search-protocol.md
source-profile rule version
```

The mutable `/retrieval-routing-policy.json` is convenient but not sufficient for historical reproducibility by itself. Use the policy copy under `/releases/<sha>/` and verify its digest against that release's manifest when exact replay matters.

The same rule applies to closed-registry chatbot search: registry, adapter file,
schema, protocol and entry must come from one immutable release. Mixing a latest
registry with an older adapter allowlist is non-compliant even if every fetch
returns HTTP 200.

This versioning contract does **not** imply runtime enforcement. `open-scholarly-sources` can publish and identify the routing policy; an external consumer can still ignore it. Compliance requires the consumer to preserve a trace showing which release and policy it actually followed. See [RETRIEVAL_ROUTING.md](RETRIEVAL_ROUTING.md).

## Self-contained release browsing

Each new immutable release is also a self-contained historical mini-site. `/releases/<sha>/` contains an `index.html`, the exact rendered homepage, the data files used by its JavaScript, generated source pages, the profile page, routing policy and schemas. Relative `./data/...`, `./sources/...` and `./profiles/...` URLs therefore resolve within the same release instead of returning 404.

The release manifest hashes these runtime files as well as the primary machine outputs. Historical releases created before this contract are not rewritten; immutability takes precedence over retroactive repair.

## Durable history

Pages artifacts are rebuilt from scratch, so old versioned directories would disappear unless they were carried forward. Successfully deployed snapshots are therefore persisted on the dedicated `release-snapshots` branch. A later Pages build imports that archive before adding its new release.

The archive write happens **after** the Pages deployment succeeds. A failed deployment is not promoted into durable release history.

`/releases/index.json` lists the retained releases and the current release ID represented by that deployed site. New entries also carry routing-policy identity; older retained entries remain historical records and are not rewritten merely to add fields that did not exist at the time.

## Freshness algorithm for agents

When current-main freshness matters:

1. Fetch `/release-manifest.json` with the machine output you are using.
2. Read `commit_sha` / `release_id`.
3. Query `repository_main_ref_api` from the manifest.
4. If the SHAs match, the fetched release represents current `main` at the time of the comparison.
5. If they differ, treat the mutable response as stale. Fetch `/releases/<main-sha>/release-manifest.json` if that release has already propagated, or retry later/fetch through a different path.
6. For a specific historical release, verify the file SHA-256 against its immutable release manifest.
7. If routing decisions must be reproduced, verify the routing-policy digest and use the policy version/method recorded by that same release; do not silently substitute the mutable latest policy.

This contract does not claim that every CDN, crawler or proxy invalidates immediately. It makes staleness **detectable, attributable and reproducible** instead of silently ambiguous.
