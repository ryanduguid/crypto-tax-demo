#!/usr/bin/env python3
"""Run the illustrative crypto calculation against the documented JSON format."""

import argparse
from pathlib import Path
import sys
import textwrap

import crypto_client
import crypto_check
from oa_client import OAClient


def run(source: str, oa: OAClient) -> bool:
    events = crypto_client.extract(source)
    plan = oa.start("Classify illustrative crypto events", "US")
    if not isinstance(plan, dict):
        raise ValueError("start must return an object")
    skills = plan.get("skills_to_load", [])
    if not isinstance(skills, list) or any(not isinstance(slug, str) for slug in skills):
        raise ValueError("skills_to_load must be an array of names")
    skill = oa.get_skill(skills[0]) if skills else {}
    complete = True
    for index, event in enumerate(events, 1):
        try:
            facts = crypto_client.normalize(event)
            verdict = crypto_check.check(facts, skill)
        except ValueError as error:
            print(f"\nEvent {index}: invalid input: {error}")
            complete = False
            continue
        amount = "unknown amount" if facts["amount"] is None else f"{facts['amount']:g}"
        print(f"\n🪙  {facts['type'] or 'unknown type'} · {facts['date'] or 'unknown date'} · "
              f"{amount} {facts['asset'] or 'unknown asset'}")
        trust = ("unverified sample rules" if verdict["provenance"] == "sample"
                 else "provider metadata; not independently verified")
        print(f"    OpenAccountants → {verdict.get('oa_skill_name') or 'crypto rules'} ({trust})")
        marker = "ℹ️" if verdict["complete"] else "⚠️"
        print(f"    {marker} {verdict['headline']}")
        print(textwrap.fill(verdict["detail"], width=96, initial_indent="       ", subsequent_indent="       "))
        if not verdict["complete"]:
            if verdict["gain"] is not None:
                print(f"       Supplied proceeds less basis: {crypto_check.money(verdict['gain'])}.")
            if verdict["term"] is not None:
                print(f"       Supplied holding term: {verdict['term']}.")
        complete = complete and verdict["complete"]
    return complete


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", default=str(Path(__file__).parent / "samples/transactions.json"))
    parser.add_argument("--live", action="store_true", help="use the unverified live adapter")
    args = parser.parse_args(argv[1:])
    oa = OAClient() if args.live else OAClient(token=None)
    if args.live and not oa.live:
        parser.error("--live requires OA_MCP_TOKEN")
    mode = "LIVE ADAPTER (unverified)" if oa.live else "BUNDLED ILLUSTRATIVE RULES"
    print(f"crypto → OpenAccountants · event demo [{mode}]")
    try:
        complete = run(args.source, oa)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Calculation failed: {error}", file=sys.stderr)
        return 2
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
