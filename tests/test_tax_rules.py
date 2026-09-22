import ast
from pathlib import Path
import unittest


def bundled_skill():
    # Read only the literal fixture; do not initialise authenticated clients.
    tree = ast.parse(Path("oa_client.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "_MOCK_SKILL" for t in node.targets):
            return next(iter(ast.literal_eval(node.value).values()))
    raise AssertionError("Missing bundled rule fixture")

import crypto_check


class CalendarHoldingPeriodTests(unittest.TestCase):
    def event(self, acquired, sold, kind="sell"):
        return {"type": kind, "is_disposal": True, "acquire_date": acquired, "date": sold,
                "asset": "BTC", "amount": 1, "cost_basis_usd": 100, "proceeds_usd": 200, "received": "ETH"}

    def test_anniversaries_and_leap_years(self):
        for acquired, sold, expected in [("2024-02-28", "2025-02-27", False),
         ("2024-02-28", "2025-02-28", False),
         ("2024-02-28", "2025-03-01", True),
         ("2023-02-28", "2024-02-28", False),
         ("2023-02-28", "2024-02-29", True),
         ("2024-02-29", "2025-02-28", False),
         ("2024-02-29", "2025-03-01", True),
         ("2024-12-31", "2025-12-31", False),
         ("2024-12-31", "2026-01-01", True)]:
            for kind in ("sell", "swap", "spend"):
                with self.subTest(acquired=acquired, sold=sold, kind=kind):
                    result=crypto_check.check(self.event(acquired, sold, kind), bundled_skill())
                    self.assertEqual("long-term" in result["headline"], expected)

    def test_invalid_dates_keep_taxable_disposal_but_not_a_guessed_term(self):
        for acquired, sold in [(None, "2025-03-01"), ("bad", "2025-03-01"), ("2025-03-01", "2024-03-01")]:
            result=crypto_check.check(self.event(acquired, sold, "swap"), bundled_skill())
            self.assertIn("taxable disposal", result["headline"])
            self.assertIn("unclassified", result["headline"])

    def test_non_disposal_paths(self):
        self.assertIn("not a taxable event", crypto_check.check(self.event(None, None, "buy"), bundled_skill())["headline"])
        self.assertIn("ordinary income", crypto_check.check(self.event(None, None, "reward"), bundled_skill())["headline"])
