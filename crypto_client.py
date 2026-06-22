"""Crypto transaction history -> normalized tax events.

Reads a transaction history (the shape you get from an exchange CSV export, a
Rotki export, or an onchain pull via Etherscan/Covalent) and normalizes each
event so the tax check can classify it. Disposals carry the cost basis and
acquisition date the tracking tool already computed.

Event types: buy, sell, swap (crypto->crypto), spend (crypto->goods), reward.
"""

from __future__ import annotations

import json
import os

# Live mode could pull onchain data via a free key; left as a documented seam.
ETHERSCAN_API_KEY = os.environ.get("ETHERSCAN_API_KEY")


def extract(source: str) -> list[dict]:
    with open(source) as fh:
        data = json.load(fh)
    return data if isinstance(data, list) else [data]


def normalize(ev: dict) -> dict:
    """Uniform shape: a disposal (taxable) or a non-disposal event."""
    t = ev.get("type", "").lower()
    disposal = t in ("sell", "swap", "spend")
    return {
        "type": t,
        "date": ev.get("date", ""),
        "asset": ev.get("asset") or ev.get("asset_out", ""),
        "amount": float(ev.get("amount") or ev.get("amount_out", 0)),
        "received": ev.get("asset_in") or ("USD" if t == "sell" else ev.get("received", "")),
        "proceeds_usd": float(ev.get("proceeds_usd", ev.get("fmv_usd", 0))),
        "cost_basis_usd": float(ev.get("cost_basis_usd", 0)),
        "acquire_date": ev.get("acquire_date", ""),
        "is_disposal": disposal,
    }
