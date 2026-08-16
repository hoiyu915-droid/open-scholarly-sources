#!/usr/bin/env python3
"""Publish the versioned retrieval-routing policy into a built site."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "data" / "retrieval-routing-policy.json"
SCHEMA = ROOT / "schemas" / "retrieval-routing-policy.schema.json"


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
    print(
        "Routing policy published: "
        f"version={policy['policy_version']} method={policy['method']} output={destination}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
