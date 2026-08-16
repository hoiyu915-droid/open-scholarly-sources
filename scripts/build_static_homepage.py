#!/usr/bin/env python3
"""Inject a compact no-JS/crawler-readable source table into the generated homepage."""

from __future__ import annotations
import argparse, html, json
from pathlib import Path

MARKER = "<!-- STATIC_FALLBACK -->"

def load(p):
    return json.loads(p.read_text(encoding="utf-8"))

def build(site: Path):
    reg = load(site / "registry.json")
    sources = reg.get("sources") or []
    if not sources:
        raise SystemExit("registry.json contains no sources")
    rows = []
    for s in sorted(sources, key=lambda x: ((x.get("source_profile") or {}).get("tier", "Z"), x["name"].casefold())):
        p = s.get("source_profile") or {}
        zh = (s.get("translation") or {}).get("zh-TW") or {}
        subjects = " · ".join(html.escape(x) for x in (s.get("subjects") or []))
        char = (p.get("character") or {}).get("zh-TW") or (p.get("character") or {}).get("en") or ""
        evidence = s.get("verification", {}).get("evidence_url", "#")
        rows.append(
            f'<tr><td><a href="./sources/{html.escape(s["id"])}.html"><b>{html.escape(s["name"])}</b></a>'
            + (f'<br><small>{html.escape(zh.get("name",""))}</small>' if zh.get("name") else "")
            + f'</td><td><b>{html.escape(p.get("tier","—"))}</b><br><small>{html.escape(char)}</small></td>'
            + f'<td>{subjects}</td><td>{html.escape(s.get("source_type",""))}</td>'
            + f'<td><a href="{html.escape(evidence)}">{html.escape(s.get("verification",{}).get("status",""))}</a>'
            + f'<br><small>{html.escape(s.get("verification",{}).get("checked",""))}</small></td></tr>'
        )
    block = '''<section class="static-fallback" aria-label="Static source fallback">
    <h2>Static source index / 無 JavaScript 來源索引</h2>
    <p>This compact table is generated at deploy time so crawlers, text-only clients and agents that do not execute JavaScript still receive source names, tiers, subjects and verification links. The interactive table below adds filters and richer metadata when JavaScript is available. ／ 這份表在部署時直接寫進 HTML，無需 JavaScript 也能讀取。</p>
    <div class="table-wrap"><table><thead><tr><th>Source</th><th>Tier / character</th><th>Subjects</th><th>Type</th><th>Verification</th></tr></thead>
    <tbody>''' + "".join(rows) + '''</tbody></table></div>
  </section>'''
    page = site / "index.html"
    text = page.read_text(encoding="utf-8")
    if MARKER not in text:
        raise SystemExit("homepage STATIC_FALLBACK marker missing")
    page.write_text(text.replace(MARKER, block, 1), encoding="utf-8")
    print(f"Static homepage fallback OK: {len(sources)} sources")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--site", type=Path, required=True)
    a = p.parse_args()
    build(a.site)

if __name__ == "__main__":
    main()
