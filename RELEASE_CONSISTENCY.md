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

`registry.json`, `source-profiles.json`, the homepage and both LLM text files are stamped with the full release commit SHA. NDJSON remains one source record per line and is paired with the release manifest instead of inserting a metadata line. The routing-policy and chatbot-search files carry their own version/method identity; their immutable SHA-256, byte-size and Git blob SHA-1 identities are recorded by the same release manifest.

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

The release manifest records the commit identity, source count, profile-rule identity, routing-policy identity, chatbot-search protocol/method/schema/adapter count, the registry-brokered source count and default mode, and SHA-256, byte-size and Git blob SHA-1 identity for every immutable file. `release-manifest.json` is intentionally not listed in its own `files` map because that would be self-referential; its identities are anchored by the matching entry in `/releases/index.json`.

The release-manifest schema is `4.0.0` for releases carrying the GitHub connector and registry-brokered chatbot identity. This is an intentional breaking schema bump from `3.0.0`: Git blob identity, brokered source count, default mode and the connector-compatible main-ref API are required, so the repository does not pretend the contract is backward-compatible merely because they are additive in JSON syntax.

The release index schema is `1.3.0`. Its current-release entry carries `manifest_sha256` and `manifest_git_blob_sha1` so a GitHub connector can authenticate the manifest before using that manifest to authenticate the remaining immutable files. The same entry also carries `chatbot_search_brokered_source_count` and `chatbot_search_default_mode`. Older retained entries may lack fields introduced after their original publication and remain historical records.

A release directory is append-only by identity. If a future deployment tries to reuse an existing commit SHA with different bytes, the archive step fails instead of overwriting the old release.

## Registry-brokered chatbot identity

The default chatbot route is the generic registry-brokered v2 flow: a Chatbot
uses the GitHub connector to pin one immutable release, selects active registry
sources, uses a domain-restricted web search only as a discovery broker, and
opens the selected registered source before making content claims. The broker's
snippets are not evidence. The strict topic-search adapters remain optional
secondary routes for consumers that explicitly choose `registry_closed` or
`direct_only`; they are not the default release identity.

The release identity for this flow includes:

```text
chatbot_search_protocol_version
chatbot_search_method
chatbot_search_schema_version
chatbot_search_adapter_count
chatbot_search_brokered_source_count
chatbot_search_default_mode
```

The release manifest and the current release-index entry must agree on the two
brokered fields. A consumer must not infer the brokered source count from a
different release's routing file.

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

The same rule applies to registry-brokered chatbot search: registry, routing
file, schema, protocol and entry must come from one immutable release. Mixing a
latest registry with an older broker/default-mode declaration or strict-adapter
allowlist is non-compliant even if every fetch returns HTTP 200.

This versioning contract does **not** imply runtime enforcement. `open-scholarly-sources` can publish and identify the routing policy; an external consumer can still ignore it. Compliance requires the consumer to preserve a trace showing which release and policy it actually followed. See [RETRIEVAL_ROUTING.md](RETRIEVAL_ROUTING.md).

## Self-contained release browsing

Each new immutable release is also a self-contained historical mini-site. `/releases/<sha>/` contains an `index.html`, the exact rendered homepage, the data files used by its JavaScript, generated source pages, the profile page, routing policy and schemas. Relative `./data/...`, `./sources/...` and `./profiles/...` URLs therefore resolve within the same release instead of returning 404.

The release manifest hashes these runtime files as well as the primary machine outputs. Historical releases created before this contract are not rewritten; immutability takes precedence over retroactive repair.

## Durable history

Pages artifacts are rebuilt from scratch, so old versioned directories would disappear unless they were carried forward. Successfully deployed snapshots are therefore persisted on the dedicated `release-snapshots` branch. A later Pages build imports that archive before adding its new release.

The archive write happens **after** the Pages deployment succeeds. A failed deployment is not promoted into durable release history.

`/releases/index.json` lists the retained releases and the current release ID represented by that deployed site. New entries carry routing-policy identity, brokered source/default-mode identity and manifest SHA-256/Git blob anchors; older retained entries remain historical records and are not rewritten merely to add fields that did not exist at the time.

## GitHub connector freshness algorithm

When current-main freshness matters, a connector-capable consumer should use
the repository's `/branches/main` endpoint recorded in the release manifest:

1. Read `releases/index.json` from the `release-snapshots` branch through the GitHub connector.
2. Query `repository_main_ref_api`, which must be `https://api.github.com/repos/<owner>/<repo>/branches/main`, and read the resolved main commit SHA.
3. Select the one index entry whose `release_id` and `commit_sha` equal that main SHA.
4. Fetch that entry's immutable `releases/<sha>/release-manifest.json` and compare its SHA-256 and Git blob SHA-1 with the index entry.
5. Verify every required immutable file's SHA-256, byte count and Git blob SHA-1 against that manifest. Do not use a mutable Pages response as a substitute.
6. For a specific historical release, perform the same manifest/index identity checks for the requested commit-addressed directory.
7. If the index and main branch disagree, stop with a publication/freshness gap; do not silently substitute the mutable latest policy or routing file.

This contract does not claim that every CDN, crawler or proxy invalidates immediately. It makes staleness **detectable, attributable and reproducible** instead of silently ambiguous.
