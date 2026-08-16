# Agent contract for Open Scholarly Sources

This file defines the **default behavior for LLMs and research agents** using this repository.

## Default behavior

Open Scholarly Sources is a **source-navigation registry**.

When a user asks to find literature, OA sources, journals, repositories, proceedings or places to search:

1. Read the pinned registry / source profiles.
2. Select a small number of relevant registered sources.
3. Prefer roughly 5 sources; do not exceed 8 unless the user asks for broader coverage.
4. Explain briefly why each source is useful for the topic.
5. Point to the registered canonical URL.
6. Stop.

### Do not do this by default

Do **not** automatically:

- resolve candidate DOIs;
- call Crossref, DOAJ or Unpaywall for verification;
- build resolution attestations;
- classify documents as `formal_evidence`, `discovery_only` or `unresolved`;
- open public-ocean fallback because a journal is missing from the registry;
- reject otherwise useful literature merely because the exact journal is not a canonical registry entity.

A normal request to **find/search/recommend literature** is not a verification request.

## Verification is explicit opt-in

Only activate the verification route when the user explicitly asks for actions such as:

- 核實這些文獻
- 驗證來源
- 啟動認證路由
- 跑 verification gate
- 做 source audit
- check these papers formally

Do not infer opt-in merely because the topic is biomedical, high stakes, controversial, recent or important. Host-level safety/compliance rules may independently require checks, but that is outside this repository's default routing contract.

When verification is explicitly enabled, follow `RETRIEVAL_ROUTING.md` and the pinned `data/retrieval-routing-policy.json`.

## Default flow

```text
user topic
→ Open Scholarly Sources registry
→ select relevant registered sources
→ tell the user where to dig and why
→ stop
```

## Optional verification flow

```text
explicit user verification request
→ verification.enabled=true
→ registry-first verification route
→ resolution gate
→ coverage check
→ public ocean only when the verification policy permits
→ public-ocean candidates return through the same gate
```

## Regression invariant

A literature-search request must not collapse to zero useful results merely because candidate papers are published in journals that are not represented as exact journal-level registry entities.

That gate behavior belongs only to explicit verification.
