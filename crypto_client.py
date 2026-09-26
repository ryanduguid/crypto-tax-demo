"""Read the documented JSON event format; no CSV or exchange API adapter is included."""

from datetime import date
from decimal import Decimal, InvalidOperation
import json

DISPOSALS = {"sell", "swap", "spend"}
EVENTS = DISPOSALS | {"buy", "reward"}


def number(value, field):
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a number, not a Boolean")
    try:
        result = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError(f"{field} must be a decimal number") from error
    if not result.is_finite() or result < 0 or result > Decimal("1e12"):
        raise ValueError(f"{field} must be finite and between 0 and 1e12")
    if result.as_tuple().exponent < -18:
        raise ValueError(f"{field} supports at most 18 decimal places")
    return result


def text(value, field):
    if value is not None and not isinstance(value, str):
        raise ValueError(f"{field} must be text")
    return value.strip() if value is not None else None


def boolean(value, field):
    if value is not None and not isinstance(value, bool):
        raise ValueError(f"{field} must be true, false or null")
    return value


def calendar_date(value, field):
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must use YYYY-MM-DD")
    try:
        result = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{field} must be a valid YYYY-MM-DD date") from error
    if result.isoformat() != value:
        raise ValueError(f"{field} must use YYYY-MM-DD")
    return result


def alias(event, primary, alternate, convert):
    value = convert(event.get(primary), primary)
    fallback = convert(event.get(alternate), alternate)
    if primary in event and alternate in event and value != fallback:
        raise ValueError(f"{primary} and {alternate} conflict")
    return value if primary in event else fallback


def extract(source: str) -> list[dict]:
    with open(source, encoding="utf-8") as fh:
        try:
            data = json.load(fh, parse_float=Decimal)
        except InvalidOperation as error:
            raise ValueError("invalid JSON decimal literal") from error
    if data == []:
        raise ValueError("input must contain at least one record")
    return data if isinstance(data, list) else [data]


def normalize(ev: dict) -> dict:
    if not isinstance(ev, dict):
        raise ValueError("each event must be an object")
    kind = (text(ev.get("type"), "type") or "").lower()
    disposal = kind in DISPOSALS
    supplied_disposal = boolean(ev.get("is_disposal"), "is_disposal")
    if supplied_disposal is not None and supplied_disposal != disposal:
        raise ValueError("is_disposal contradicts the event type")
    if ev.get("lots") is not None:
        raise ValueError("provide a separate event for each acquisition lot")
    acquired = calendar_date(ev.get("acquire_date"), "acquire_date")
    occurred = calendar_date(ev.get("date"), "date")
    if acquired is not None and occurred is not None and occurred < acquired:
        raise ValueError("date precedes acquire_date")
    method = text(ev.get("acquisition_method"), "acquisition_method")
    cash = boolean(ev.get("paid_with_cash"), "paid_with_cash")
    if kind == "buy" and cash is True and method not in (None, "", "purchase"):
        raise ValueError("cash purchase contradicts acquisition_method")
    return {
        "type": kind, "date": occurred, "acquire_date": acquired,
        "asset": alias(ev, "asset", "asset_out", text),
        "amount": alias(ev, "amount", "amount_out", number),
        "received": alias(ev, "received", "asset_in", text),
        "proceeds_usd": alias(ev, "proceeds_usd", "fmv_usd", number),
        "cost_basis_usd": number(ev.get("cost_basis_usd"), "cost_basis_usd"),
        "is_disposal": disposal,
        "acquisition_method": method,
        "paid_with_cash": cash,
        "reward_kind": text(ev.get("reward_kind"), "reward_kind"),
        "dominion_and_control": boolean(ev.get("dominion_and_control"), "dominion_and_control"),
    }
