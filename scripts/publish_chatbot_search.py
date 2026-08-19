#!/usr/bin/env python3
"""Publish the static chatbot search entry, protocol and routing contract."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTING = ROOT / "data" / "chatbot-search-routing.json"
PROTOCOL = ROOT / "CHATBOT_OA_SEARCH_PROTOCOL.md"
SCHEMA = ROOT / "schemas" / "chatbot-search-routing.schema.json"
ENTRY = ROOT / "chatbot-entry.txt"
GUIDANCE_MARKER = "## Registry-brokered OA search for chatbots"
GUIDANCE = """
## Registry-brokered OA search for chatbots

- Use the GitHub connector to pin `main` to one immutable `release-snapshots/releases/<sha>/` directory; do not mix releases or use Pages as the default bootstrap.
- Select active sources dynamically from the pinned registry. Derive each broker domain from that selected source's exact HTTPS `canonical_url` hostname; do not use a hard-coded source list.
- A domain-restricted web search is a discovery broker only. Search snippets and cached result text are not evidence.
- Open only an exact-canonical-host candidate and verify the original container/source identity before using the evidence scope allowed by the registry record.
- Preserve broker, identity, original-fetch, adapter and registry coverage gaps; none means “no literature exists.”
- Strict adapters remain optional secondary checks. This protocol requires no Skill, MCP, Radar or custom server and does not claim runtime firewall enforcement.

中文：Chatbot 由同一 immutable registry 動態選來源，再把來源的 canonical host 當作網搜 domain filter；網搜只負責找路，snippet 不是證據，必須開啟並核對原始登錄來源。
""".lstrip()


def inject_guidance(path: Path) -> None:
    if not path.is_file():
        raise SystemExit(f"LLM output missing before chatbot search publication: {path.name}")
    text = path.read_text(encoding="utf-8")
    if GUIDANCE_MARKER in text:
        return
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text + "\n" + GUIDANCE, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    for path in (ROUTING, PROTOCOL, SCHEMA, ENTRY):
        if not path.is_file():
            raise SystemExit(f"chatbot search input missing: {path.relative_to(ROOT)}")
    routing = json.loads(ROUTING.read_text(encoding="utf-8"))
    if routing.get("method") is None or routing.get("protocol_version") is None:
        raise SystemExit("chatbot search identity missing")

    args.output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROUTING, args.output / "chatbot-search-routing.json")
    shutil.copy2(PROTOCOL, args.output / "chatbot-search-protocol.md")
    shutil.copy2(ENTRY, args.output / "chatbot-entry.txt")
    for filename in ("llms.txt", "llms-full.txt"):
        inject_guidance(args.output / filename)

    print(
        "Chatbot search published: "
        f"protocol={routing['protocol_version']} adapters={len(routing['adapters'])} "
        f"brokered_sources={routing['brokered_discovery']['eligible_source_count']} "
        f"output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
