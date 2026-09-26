"""Calculate supported illustrative US crypto events from normalised input facts."""

from decimal import Decimal, ROUND_HALF_UP, localcontext

from crypto_client import DISPOSALS, EVENTS


def holding_term(acquired, disposed):
    if acquired is None or disposed is None:
        return None
    if disposed < acquired:
        raise ValueError("disposal precedes acquisition")
    # ponytail: Leap-day acquisitions need a verified calendar boundary before classification.
    if (acquired.month, acquired.day) == (2, 29):
        return None
    boundary = (acquired.year + 1, acquired.month, acquired.day)
    return "long-term" if (disposed.year, disposed.month, disposed.day) > boundary else "short-term"


def money(value):
    with localcontext() as context:
        context.prec = 50
        return f"${value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"


def check(ev: dict, oa_skill: dict) -> dict:
    rules = oa_skill.get("rules", {})
    base = {
        "oa_skill": oa_skill.get("slug"), "oa_skill_name": oa_skill.get("name"),
        "provenance": oa_skill.get("provenance", "unverified"),
        "reported_metadata": {key: oa_skill.get(key) for key in ("tier", "verifier", "source")},
        "complete": False, "gain": None, "term": None, "holding_days": None, "income": None,
    }
    kind = ev["type"]
    proceeds, basis = ev.get("proceeds_usd"), ev.get("cost_basis_usd")
    if kind in DISPOSALS and proceeds is not None and basis is not None:
        with localcontext() as context:
            context.prec = 50
            base["gain"] = proceeds - basis
    expected = {"schema": "ordinary-us-crypto-v1", "holding_period": "more_than_calendar_year",
                "taxable_disposals": ["sell", "swap", "spend"],
                "reward_policy": "staking_or_hard_fork_airdrop_with_control"}
    if not isinstance(rules, dict) or rules != expected:
        return {**base, "status": "incomplete", "headline": "Unsupported rule contract",
                "detail": "The loaded rules do not match the supported illustrative calculation."}
    if kind not in EVENTS:
        return {**base, "status": "incomplete", "headline": "Unsupported event type",
                "detail": "Use the documented buy, sell, swap, spend or reward format."}
    missing = []
    for key in ("asset", "amount", "date"):
        if ev.get(key) is None or ev.get(key) == "":
            missing.append(key)
    if kind == "buy":
        if ev.get("paid_with_cash") is not True:
            missing.append("explicit cash-payment confirmation")
        if ev.get("cost_basis_usd") is None:
            missing.append("cost_basis_usd")
        headline = "Cash acquisition under the supplied facts"
        detail = "A supported cash purchase creates no disposal gain in this example."
    elif kind == "reward":
        if ev.get("reward_kind") not in ("staking", "hard_fork_airdrop"):
            missing.append("supported reward_kind")
        if ev.get("dominion_and_control") is not True:
            missing.append("dominion-and-control confirmation")
        if ev.get("proceeds_usd") is None:
            missing.append("receipt fair market value")
        if not missing:
            base["income"] = ev["proceeds_usd"]
        headline = "Reward receipt under the supplied facts"
        detail = ("The example treats the supplied receipt value as ordinary income when control is established."
                  " The input date must be the date that control was obtained.")
    else:
        if proceeds is None:
            missing.append("proceeds_usd")
        if basis is None:
            missing.append("cost_basis_usd")
        if ev.get("acquisition_method") != "purchase":
            missing.append("ordinary-purchase acquisition_method")
        else:
            base["term"] = holding_term(ev.get("acquire_date"), ev.get("date"))
            if base["term"] is None:
                missing.append("supported acquisition and disposal dates")
        if ev.get("acquire_date") is not None and ev.get("date") is not None:
            base["holding_days"] = (ev["date"] - ev["acquire_date"]).days
        if kind == "swap" and not ev.get("received"):
            missing.append("asset received in the swap")
        headline = f"{kind.capitalize()} disposal"
        detail = "Uses supplied USD proceeds and adjusted basis, including any applicable fee adjustments."
    if missing:
        return {**base, "status": "incomplete", "headline": f"{headline}: incomplete",
                "detail": "Missing or unsupported facts: " + ", ".join(missing) + ".",
                "missing": missing}
    if kind in DISPOSALS:
        gain = base["gain"]
        outcome = "no gain or loss" if gain == 0 else f"{money(gain.copy_abs())} {'gain' if gain > 0 else 'loss'}"
        headline += f": {base['term']}, {outcome}"
        detail += f" Held {base['holding_days']} days; the term uses a calendar year."
    elif kind == "reward":
        detail += f" Illustrative income: {money(base['income'])}."
    else:
        detail += f" Supplied adjusted basis: {money(ev['cost_basis_usd'])}."
    return {**base, "complete": True, "status": "info", "headline": headline, "detail": detail}
