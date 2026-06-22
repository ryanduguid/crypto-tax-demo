#!/usr/bin/env python3
"""crypto transaction history -> OpenAccountants crypto-tax pipeline.

    python pipeline.py                      # bundled sample history (mock mode)
    python pipeline.py samples/transactions.json

The flow:
    crypto events -> OA MCP (start -> get_skill) -> classify each event -> verdict

Works with an exchange CSV export, a Rotki export, or an onchain pull. Set
OA_MCP_TOKEN to use the live verified rules.
"""

from __future__ import annotations

import os
import sys

import crypto_client
import crypto_check
from oa_client import OAClient

STATUS = {"ok": "✅", "warn": "⚠️ ", "info": "ℹ️ "}


def run(source: str, oa: OAClient) -> None:
    events = crypto_client.extract(source)
    plan = oa.start("Classify crypto tax events", "US")
    slug = (plan.get("skills_to_load") or [None])[0]
    skill = oa.get_skill(slug) if slug else {}

    for ev in events:
        f = crypto_client.normalize(ev)
        if f["type"] == "swap":
            line = f"{f['amount']:g} {f['asset']} → {f['received']}"
        elif f["type"] == "buy":
            line = f"{f['amount']:g} {f['asset']} for cash"
        elif f["type"] == "reward":
            line = f"{f['amount']:g} {f['asset']} reward"
        else:
            line = f"{f['amount']:g} {f['asset']}"
        print(f"\n🪙  {f['type']} · {f['date']} · {line}")

        v = crypto_check.check(f, skill)
        trust = f"tier {v.get('tier')}" + (f", signed off by {v['verifier']}" if v.get("verifier") else "")
        print(f"    OpenAccountants → {v.get('oa_skill_name') or 'crypto-tax rules'}  ({trust})")
        print(f"    {STATUS.get(v['status'], '')} {v['headline']}")
        if v["detail"]:
            print(f"       {v['detail']}")


def main(argv: list[str]) -> int:
    oa = OAClient()
    mode = "LIVE" if oa.live else "MOCK (set OA_MCP_TOKEN to use the live verified rules)"
    print(f"crypto → OpenAccountants · crypto-tax demo  [{mode}]")
    here = os.path.dirname(os.path.abspath(__file__))
    source = argv[1] if len(argv) > 1 else os.path.join(here, "samples", "transactions.json")
    run(source, oa)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
