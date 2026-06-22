"""Classify a crypto event against the loaded OA crypto-tax rules.

The catches people miss:
  - a crypto-to-crypto **swap** is a taxable disposal at fair value (no cash needed)
  - **spending** crypto is a disposal too
  - **staking/airdrop rewards** are ordinary income at receipt
A plain **sell** is taxable as well (short/long term); a **buy** is not.

DELIBERATE SCOPE: classification + gain + term, not an exact tax figure (needs
total income, filing status, NIIT, wash-sale nuances). Production leans on the
full OA skill + an agent step; the named-CPA sign-off makes it relianceable.
"""

from __future__ import annotations

from datetime import date


def _days(a: str, b: str) -> int | None:
    try:
        ay, am, ad = map(int, a.split("-"))
        by, bm, bd = map(int, b.split("-"))
        return (date(by, bm, bd) - date(ay, am, ad)).days
    except Exception:
        return None


def check(ev: dict, oa_skill: dict) -> dict:
    rules = oa_skill.get("rules", {})
    base = {"oa_skill": oa_skill.get("slug"), "oa_skill_name": oa_skill.get("name"),
            "tier": oa_skill.get("tier"), "verifier": oa_skill.get("verifier")}
    t = ev["type"]

    if t == "buy":
        return {**base, "status": "info", "headline": "Acquisition — not a taxable event",
                "detail": f"Buying {ev['asset']} with cash isn't taxable; it sets your cost basis (${ev['cost_basis_usd']:,.2f})."}

    if t == "reward":
        return {**base, "status": "warn", "headline": "Staking/airdrop reward — ordinary income",
                "detail": f"${ev['proceeds_usd']:,.2f} of {ev['asset']} is ordinary income at fair value on receipt (and sets basis for a later disposal)."}

    if not ev["is_disposal"]:
        return {**base, "status": "info", "headline": "Non-taxable event", "detail": ""}

    # Disposal: sell / swap / spend
    gain = round(ev["proceeds_usd"] - ev["cost_basis_usd"], 2)
    days = _days(ev["acquire_date"], ev["date"])
    term = "long-term" if (days is not None and days >= rules.get("long_term_min_days", 366)) else "short-term"
    term_note = f"{term}" + (f" (held {days} days)" if days is not None else "")
    sign = "gain" if gain >= 0 else "loss"

    if t == "swap":
        return {**base, "status": "warn",
                "headline": f"Crypto-to-crypto swap is a taxable disposal — ${gain:,.2f} {term} {sign}",
                "detail": f"Swapping {ev['amount']:g} {ev['asset']} for {ev['received']} disposes of the {ev['asset']} at fair value — taxable even though no cash was received. {term_note}."}
    if t == "spend":
        return {**base, "status": "warn",
                "headline": f"Spending crypto is a taxable disposal — ${gain:,.2f} {term} {sign}",
                "detail": f"Paying with {ev['amount']:g} {ev['asset']} disposes of it at fair value — taxable even though it's a purchase. {term_note}."}
    # plain sell
    status = "ok" if gain >= 0 and term == "long-term" else "info"
    return {**base, "status": status,
            "headline": f"Sale — ${gain:,.2f} {term} {sign}",
            "detail": f"Disposed of {ev['amount']:g} {ev['asset']} for ${ev['proceeds_usd']:,.2f}. {term_note}."}
