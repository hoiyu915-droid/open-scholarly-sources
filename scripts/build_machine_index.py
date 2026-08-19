#!/usr/bin/env python3
"""Build consolidated and LLM/search-discoverable outputs for GitHub Pages."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape as xml_escape

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MANIFEST_PATH = DATA / "registry-manifest.json"
DEFAULT_BASE_URL = "https://hoiyu915-droid.github.io/open-scholarly-sources"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def merge_registry():
    manifest = load(MANIFEST_PATH)
    sources = []
    for filename in manifest["source_shards"]:
        sources.extend(load(DATA / filename)["sources"])

    taxonomy: dict[str, dict[str, str]] = {}
    translations: dict[str, dict[str, str]] = {}
    for filename in manifest["translation_shards"]:
        shard = load(DATA / filename)
        for group, mapping in shard["taxonomy"].items():
            taxonomy.setdefault(group, {}).update(mapping)
        translations.update(shard["sources"])

    sources.sort(key=lambda source: (source["name"].casefold(), source["id"]))
    return manifest, sources, taxonomy, translations


def label(value: str) -> str:
    return value.replace("_", " ")


def bilingual(taxonomy, group: str, value: str) -> str:
    zh = taxonomy.get(group, {}).get(value)
    return f"{label(value)} / {zh}" if zh else label(value)


def policy_lines(source, taxonomy):
    policy = source.get("access_policy")
    if not policy:
        return []
    lines = [
        f"OA model: {bilingual(taxonomy, 'oa_models', policy['model'])}",
        f"Effective from: {policy['effective_from'] or 'not specified'}",
        f"Verified open years: {', '.join(policy['open_years']) or 'not year-specific'}",
        f"Backfile: {bilingual(taxonomy, 'backfile_scopes', policy['backfile_scope'])}",
        "Version scope: " + ", ".join(
            bilingual(taxonomy, "version_scopes", value) for value in policy["version_scope"]
        ),
        f"Licence scope: {bilingual(taxonomy, 'license_scopes', policy['license_scope'])}",
    ]
    if policy.get("notes"):
        lines.append(f"Policy note: {policy['notes']}")
    return lines


def consolidated_record(source, taxonomy, translations, base_url):
    zh = translations[source["id"]]
    record = dict(source)
    record["translation"] = {"zh-TW": zh}
    record["localized_subjects"] = {
        "zh-TW": [taxonomy["subjects"][subject] for subject in source["subjects"]]
    }
    record["registry_page"] = f"{base_url}/sources/{source['id']}.html"
    return record


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_jsonld(manifest, records, base_url):
    parts = []
    for record in records:
        part = {
            "@type": "CreativeWork",
            "@id": record["registry_page"] + "#source",
            "identifier": record["id"],
            "name": record["name"],
            "alternateName": record["translation"]["zh-TW"]["name"],
            "description": record["notes"],
            "url": record["registry_page"],
            "sameAs": record["canonical_url"],
            "about": record["subjects"],
            "inLanguage": ["en", "zh-Hant"],
            "isAccessibleForFree": record["oa_scope"] == "full",
            "dateModified": record["verification"]["checked"],
        }
        if record.get("parent_id"):
            part["isPartOf"] = {
                "@id": f"{base_url}/sources/{record['parent_id']}.html#source"
            }
        parts.append(part)

    return {
        "@context": "https://schema.org",
        "@type": "DataCatalog",
        "@id": base_url + "/#catalog",
        "name": "Open Scholarly Sources",
        "alternateName": "開放學術來源",
        "description": (
            "A bilingual, evidence-backed registry of open scholarly journals, proceedings, "
            "platforms, repositories, directories and preprint sources."
        ),
        "url": base_url + "/",
        "inLanguage": ["en", "zh-Hant"],
        "dateModified": manifest["updated"],
        "license": "https://www.apache.org/licenses/LICENSE-2.0",
        "distribution": [
            {
                "@type": "DataDownload",
                "encodingFormat": "application/json",
                "contentUrl": base_url + "/registry.json",
            },
            {
                "@type": "DataDownload",
                "encodingFormat": "application/x-ndjson",
                "contentUrl": base_url + "/registry.ndjson",
            },
            {
                "@type": "DataDownload",
                "encodingFormat": "application/ld+json",
                "contentUrl": base_url + "/registry.jsonld",
            },
            {
                "@type": "DataDownload",
                "encodingFormat": "application/json",
                "contentUrl": base_url + "/chatbot-search-routing.json",
            },
        ],
        "dataset": {
            "@type": "Dataset",
            "@id": base_url + "/#dataset",
            "name": "Open Scholarly Sources registry",
            "dateModified": manifest["updated"],
            "size": len(records),
            "hasPart": parts,
        },
    }


def source_html(source, taxonomy, translations, base_url):
    zh = translations[source["id"]]
    title = f"{source['name']}｜{zh['name']} — Open Scholarly Sources"
    subjects = " · ".join(
        html.escape(bilingual(taxonomy, "subjects", subject)) for subject in source["subjects"]
    )
    roles = " · ".join(
        html.escape(bilingual(taxonomy, "access_roles", role)) for role in source["access_roles"]
    )
    policy = source.get("access_policy")
    policy_html = ""
    if policy:
        rows = []
        for line in policy_lines(source, taxonomy):
            key, _, value = line.partition(": ")
            rows.append(f"<dt>{html.escape(key)}</dt><dd>{html.escape(value)}</dd>")
        policy_html = "<section><h2>Access policy / 存取政策</h2><dl>" + "".join(rows) + "</dl></section>"

    machine = source.get("machine_access", {})
    endpoints = [
        ("Feed", machine.get("feed_url")),
        ("API", machine.get("api_url")),
        ("OAI-PMH", machine.get("oai_pmh_url")),
        ("Bulk metadata", machine.get("bulk_metadata_url")),
    ]
    endpoint_html = " · ".join(
        f'<a rel="nofollow" href="{html.escape(url, quote=True)}">{html.escape(name)}</a>'
        for name, url in endpoints if url
    ) or "No verified endpoint registered / 尚未登錄已驗證端點"

    jsonld = {
        "@context": "https://schema.org",
        "@type": "CreativeWork",
        "@id": f"{base_url}/sources/{source['id']}.html#source",
        "identifier": source["id"],
        "name": source["name"],
        "alternateName": zh["name"],
        "description": source["notes"],
        "url": f"{base_url}/sources/{source['id']}.html",
        "sameAs": source["canonical_url"],
        "about": source["subjects"],
        "inLanguage": ["en", "zh-Hant"],
        "isAccessibleForFree": source["oa_scope"] == "full",
        "dateModified": source["verification"]["checked"],
    }

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(zh['summary'], quote=True)}">
  <link rel="canonical" href="{base_url}/sources/{source['id']}.html">
  <link rel="alternate" type="application/json" href="{base_url}/registry.json">
  <script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>
  <style>
    :root {{ color-scheme: light dark; --bg:#f6f7f5; --panel:#fff; --text:#18201d; --muted:#66706b; --line:#dce2de; --accent:#176b51; }}
    @media (prefers-color-scheme:dark) {{ :root {{--bg:#0f1412;--panel:#151c19;--text:#e8eee9;--muted:#a7b2ac;--line:#2b3832;--accent:#6dd2ad;}} }}
    * {{ box-sizing:border-box; }} body {{ margin:0;background:var(--bg);color:var(--text);font:16px/1.65 ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC",sans-serif; }}
    main {{ width:min(900px,calc(100% - 28px));margin:0 auto;padding:48px 0 64px; }}
    a {{ color:var(--accent); }} article {{ background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:clamp(22px,5vw,44px); }}
    .back {{ display:inline-block;margin-bottom:24px;text-decoration:none;font-weight:700; }} h1 {{ margin:.15em 0;font-size:clamp(30px,6vw,52px);line-height:1.05; }}
    .zh {{ color:var(--muted);font-size:1.25rem;font-weight:700; }} .org,.meta {{ color:var(--muted); }}
    .summary {{ border-left:3px solid var(--accent);padding-left:14px; }} h2 {{ margin-top:2rem; }}
    dl {{ display:grid;grid-template-columns:minmax(150px,.35fr) 1fr;gap:8px 18px; }} dt {{ font-weight:750; }} dd {{ margin:0;color:var(--muted); }}
    code {{ overflow-wrap:anywhere; }} @media(max-width:600px) {{ dl {{ grid-template-columns:1fr;gap:3px; }} dd {{ margin-bottom:10px; }} }}
  </style>
</head>
<body>
<main>
  <a class="back" href="../">← Open Scholarly Sources / 開放學術來源</a>
  <article>
    <div class="meta"><code>{html.escape(source['id'])}</code></div>
    <h1>{html.escape(source['name'])}</h1>
    <div class="zh">{html.escape(zh['name'])}</div>
    <p class="org">{html.escape(source['organization'])}</p>
    <p>{html.escape(source['notes'])}</p>
    <p class="summary">{html.escape(zh['summary'])}</p>

    <section>
      <h2>Classification / 分類</h2>
      <dl>
        <dt>Subjects / 領域</dt><dd>{subjects}</dd>
        <dt>Source type / 類型</dt><dd>{html.escape(bilingual(taxonomy, "source_types", source["source_type"]))}</dd>
        <dt>OA scope / OA 範圍</dt><dd>{html.escape(bilingual(taxonomy, "oa_scopes", source["oa_scope"]))}</dd>
        <dt>Peer review / 同儕審查</dt><dd>{html.escape(bilingual(taxonomy, "peer_review_scopes", source["peer_review_scope"]))}</dd>
        <dt>Publication state / 出版狀態</dt><dd>{html.escape(bilingual(taxonomy, "publication_states", source["publication_state"]))}</dd>
        <dt>Access roles / 存取角色</dt><dd>{roles}</dd>
        <dt>Status / 狀態</dt><dd>{html.escape(source["status"])}</dd>
      </dl>
    </section>

    {policy_html}

    <section>
      <h2>Canonical and evidence links / 正式來源與證據</h2>
      <p><a href="{html.escape(source['canonical_url'], quote=True)}">Canonical source / 正式來源</a></p>
      <p><a href="{html.escape(source['verification']['evidence_url'], quote=True)}">Verification evidence / 驗證證據</a></p>
      <p class="meta">Checked / 驗證日期：{html.escape(source['verification']['checked'])}</p>
      <p>{endpoint_html}</p>
    </section>
  </article>
</main>
</body>
</html>
"""


def llms_text(manifest, records, base_url):
    count = len(records)
    lines = [
        "# Open Scholarly Sources",
        "",
        "> Evidence-backed bilingual registry of open scholarly journals, proceedings, platforms, repositories, directories, aggregators and preprint sources.",
        "> 具證據、英繁中對照的開放學術來源登錄表。",
        "",
        f"Updated: {manifest['updated']}",
        f"Registered source entities: {count}",
        "",
        "## Preferred machine-readable resources",
        f"- [Consolidated registry JSON]({base_url}/registry.json): all source records with zh-TW translations embedded.",
        f"- [NDJSON]({base_url}/registry.ndjson): one complete source record per line.",
        f"- [JSON-LD catalog]({base_url}/registry.jsonld): Schema.org DataCatalog/Dataset representation.",
        f"- [Full LLM text]({base_url}/llms-full.txt): complete bilingual source descriptions and access semantics.",
        f"- [Registry manifest]({base_url}/data/registry-manifest.json): canonical shard list.",
        f"- [Source schema]({base_url}/schemas/source.schema.json): field contract.",
        f"- [Closed-search chatbot entry]({base_url}/chatbot-entry.txt): minimal static bootstrap with no Skill or custom server.",
        f"- [Closed-search routing JSON]({base_url}/chatbot-search-routing.json): exact source adapters and host allowlist.",
        f"- [Closed-search protocol]({base_url}/chatbot-search-protocol.md): fail-closed OA literature search procedure.",
        "",
        "## Human-readable resources",
        f"- [Searchable bilingual registry]({base_url}/)",
        f"- [Per-source HTML index]({base_url}/sources/)",
        "",
        "## Interpretation rules",
        "- `oa_scope=full` means registered content is intended to be openly accessible; it does not guarantee a single reuse licence.",
        "- `oa_scope=mixed` requires title/article/year-level verification.",
        "- `publication_state`, `peer_review_scope`, `version_scope`, and `license_scope` are separate claims.",
        "- Subscribe-to-Open records list only verified `open_years`; do not project those years forward.",
        "- Repository records may mix versions of record, accepted manuscripts and preprints.",
        "",
        "## Subject coverage",
    ]
    subjects = sorted({subject for record in records for subject in record["subjects"]})
    for subject in subjects:
        lines.append(f"- {subject}")
    return "\n".join(lines) + "\n"


def llms_full_text(manifest, records, taxonomy, base_url):
    lines = [
        "# Open Scholarly Sources — full registry",
        "",
        f"Updated: {manifest['updated']}",
        f"Entities: {len(records)}",
        "",
        "This file is generated from the canonical manifest and source shards. "
        "Every entry includes the original source URL and a verification-evidence URL.",
        "",
    ]
    for record in records:
        zh = record["translation"]["zh-TW"]
        lines.extend([
            f"## {record['name']}｜{zh['name']}",
            f"- ID: `{record['id']}`",
            f"- Registry page: {record['registry_page']}",
            f"- Organization: {record['organization']}",
            f"- Source type: {bilingual(taxonomy, 'source_types', record['source_type'])}",
            "- Subjects: " + ", ".join(
                bilingual(taxonomy, "subjects", subject) for subject in record["subjects"]
            ),
            f"- OA scope: {bilingual(taxonomy, 'oa_scopes', record['oa_scope'])}",
            f"- Peer-review scope: {bilingual(taxonomy, 'peer_review_scopes', record['peer_review_scope'])}",
            f"- Publication state: {bilingual(taxonomy, 'publication_states', record['publication_state'])}",
            "- Access roles: " + ", ".join(
                bilingual(taxonomy, "access_roles", role) for role in record["access_roles"]
            ),
            f"- Canonical URL: {record['canonical_url']}",
            f"- Verification evidence: {record['verification']['evidence_url']}",
            f"- Checked: {record['verification']['checked']}",
            f"- English note: {record['notes']}",
            f"- 繁中摘要: {zh['summary']}",
        ])
        if record.get("parent_id"):
            lines.append(f"- Parent source: `{record['parent_id']}`")
        lines.extend(f"- {line}" for line in policy_lines(record, taxonomy))
        lines.append("")
    return "\n".join(lines)


def build(output: Path, base_url: str) -> None:
    manifest, sources, taxonomy, translations = merge_registry()
    output.mkdir(parents=True, exist_ok=True)
    source_dir = output / "sources"
    source_dir.mkdir(parents=True, exist_ok=True)

    records = [
        consolidated_record(source, taxonomy, translations, base_url)
        for source in sources
    ]
    consolidated = {
        "schema_version": manifest["schema_version"],
        "updated": manifest["updated"],
        "source_count": len(records),
        "languages": ["en", "zh-TW"],
        "sources": records,
    }
    write_json(output / "registry.json", consolidated)
    (output / "registry.ndjson").write_text(
        "".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n" for record in records),
        encoding="utf-8",
    )
    write_json(output / "registry.jsonld", build_jsonld(manifest, records, base_url))
    (output / "llms.txt").write_text(llms_text(manifest, records, base_url), encoding="utf-8")
    (output / "llms-full.txt").write_text(
        llms_full_text(manifest, records, taxonomy, base_url), encoding="utf-8"
    )
    (output / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {base_url}/sitemap.xml\n", encoding="utf-8"
    )

    urls = [base_url + "/"] + [
        f"{base_url}/sources/{quote(source['id'])}.html" for source in sources
    ]
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(
            f"  <url><loc>{xml_escape(url)}</loc><lastmod>{manifest['updated']}</lastmod></url>\n"
            for url in urls
        )
        + "</urlset>\n"
    )
    (output / "sitemap.xml").write_text(sitemap, encoding="utf-8")

    index_links = []
    for source in sources:
        zh = translations[source["id"]]
        index_links.append(
            f'<li><a href="{source["id"]}.html">{html.escape(source["name"])}'
            f'｜{html.escape(zh["name"])}</a></li>'
        )
        (source_dir / f"{source['id']}.html").write_text(
            source_html(source, taxonomy, translations, base_url), encoding="utf-8"
        )
    (source_dir / "index.html").write_text(
        """<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">"""
        f"""<meta name="viewport" content="width=device-width,initial-scale=1"><title>Source index｜來源索引</title>"""
        """<style>body{font:16px/1.6 ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC",sans-serif;"""
        """max-width:1000px;margin:40px auto;padding:0 20px}li{margin:.35rem 0}a{overflow-wrap:anywhere}</style></head><body>"""
        f"""<h1>Source index｜來源索引</h1><p><a href="../">← Registry / 登錄表</a></p><p>{len(sources)} sources</p><ul>"""
        + "".join(index_links)
        + "</ul></body></html>\n",
        encoding="utf-8",
    )

    required = [
        "registry.json", "registry.ndjson", "registry.jsonld", "llms.txt",
        "llms-full.txt", "robots.txt", "sitemap.xml", "sources/index.html",
    ]
    missing = [path for path in required if not (output / path).is_file()]
    if missing:
        raise SystemExit(f"machine index build incomplete: {missing}")
    if len(list(source_dir.glob("*.html"))) != len(sources) + 1:
        raise SystemExit("per-source page count mismatch")

    print(
        f"Machine index OK: {len(records)} sources, "
        f"{len(urls)} sitemap URLs, output={output}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()
    build(args.output, args.base_url.rstrip("/"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
