#!/usr/bin/env python3
"""Publish the routing policy and agent-default guidance into a built site."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "data" / "retrieval-routing-policy.json"
SCHEMA = ROOT / "schemas" / "retrieval-routing-policy.schema.json"
GUIDANCE_MARKER = "## Default Open Scholarly Sources agent behavior"
GUIDANCE = """
## Default Open Scholarly Sources agent behavior

- Default mode is **source navigation only**: use the registry to point the user to a small number of relevant registered scholarly sources and explain where to dig for literature.
- Ordinary find/search/recommend-literature requests do **not** activate document verification.
- By default do not call Crossref, DOAJ or Unpaywall for verification, do not emit resolution attestations, do not judge document admissibility, and do not open public-ocean fallback.
- Verification is optional and requires **explicit user opt-in** such as asking to verify papers, validate sources, run the verification gate, or perform a source audit.
- When verification is explicitly enabled, follow the pinned retrieval-routing policy and `RETRIEVAL_ROUTING.md`.

中文：預設只用本 registry 指出去幾個最適合「挖文獻」的學術來源；使用者沒有明確要求核實／驗證／認證時，不要自行啟動 resolution gate。
""".lstrip()


def inject_llm_guidance(path: Path) -> None:
    if not path.is_file():
        raise SystemExit(f"LLM output missing before routing-policy publication: {path.name}")
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

    if not POLICY.is_file() or not SCHEMA.is_file():
        raise SystemExit("routing policy or schema missing")
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    if policy.get("policy_version") is None or policy.get("method") is None:
        raise SystemExit("routing policy identity missing")

    args.output.mkdir(parents=True, exist_ok=True)
    destination = args.output / "retrieval-routing-policy.json"
    shutil.copy2(POLICY, destination)

    for filename in ("llms.txt", "llms-full.txt"):
        inject_llm_guidance(args.output / filename)

    print(
        "Routing policy published: "
        f"version={policy['policy_version']} method={policy['method']} output={destination}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
