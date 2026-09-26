import copy
import contextlib
import io
from pathlib import Path
import tempfile
import os
import unittest
from decimal import Decimal, localcontext
from unittest.mock import patch

os.environ["OA_MCP_TOKEN"] = ""
os.environ["OA_MCP_URL"] = "https://example.invalid"
os.environ["ETHERSCAN_API_KEY"] = ""

import crypto_check
import crypto_client
import pipeline
from oa_client import OAClient


class EventTests(unittest.TestCase):
    def setUp(self):
        self.network = patch("urllib.request.urlopen", side_effect=AssertionError("Network forbidden"))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.socket = patch("socket.create_connection", side_effect=AssertionError("Network forbidden"))
        self.socket.start()
        self.addCleanup(self.socket.stop)
        self.skill = copy.deepcopy(OAClient(token=None).get_skill("us-crypto-tax"))
        self.event = {"type": "sell", "asset": "EXAMPLE", "amount": 1,
                      "proceeds_usd": 110, "cost_basis_usd": 100,
                      "acquire_date": "2023-03-01", "date": "2024-03-01",
                      "acquisition_method": "purchase"}

    def result(self, **changes):
        return crypto_check.check(crypto_client.normalize({**self.event, **changes}), self.skill)

    def test_calendar_anniversary(self):
        for acquired, sold, term in (("2023-03-01", "2024-03-01", "short-term"),
                                     ("2023-03-01", "2024-03-02", "long-term"),
                                     ("2024-03-01", "2025-03-01", "short-term"),
                                     ("2024-03-01", "2025-03-02", "long-term"),
                                     ("2024-03-01", "2024-03-01", "short-term")):
            with self.subTest(acquired=acquired, sold=sold):
                self.assertIn(term, self.result(acquire_date=acquired, date=sold)["headline"])

    def test_missing_date_does_not_invent_a_term(self):
        result = self.result(acquire_date=None)
        self.assertFalse(result.get("complete", True))
        self.assertIsNone(result["term"])
        self.assertEqual(result["gain"], Decimal(10))

    def test_unknown_type_is_not_non_taxable(self):
        result = self.result(type="unknown")
        self.assertFalse(result.get("complete", True))
        self.assertNotIn("Non-taxable", result["headline"])

    def test_missing_money_and_explicit_zero(self):
        self.assertFalse(self.result(cost_basis_usd=None).get("complete", True))
        self.assertFalse(self.result(proceeds_usd=None).get("complete", True))
        self.assertEqual(self.result(cost_basis_usd=0)["gain"], Decimal(110))
        self.assertEqual(self.result(proceeds_usd=0)["gain"], Decimal(-100))
        self.assertIn("no gain or loss", self.result(proceeds_usd=0, cost_basis_usd=0)["headline"])

    def test_invalid_dates_and_contradictory_flags(self):
        for changes in ({"date": "2024-02-30"}, {"date": "2022-01-01"},
                        {"is_disposal": False}, {"is_disposal": "false"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.result(**changes)

    def test_invalid_numbers(self):
        for value in (True, "NaN", "Infinity", -1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.result(amount=value)

    def test_aliases_keep_zero_and_reject_conflicts(self):
        self.assertEqual(self.result(proceeds_usd=0, fmv_usd=0)["gain"], Decimal(-100))
        for changes in ({"amount": 0, "amount_out": 5}, {"proceeds_usd": 0, "fmv_usd": 100}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.result(**changes)

    def test_unsupported_holding_rules(self):
        self.skill["rules"]["long_term_min_days"] = 366
        self.assertFalse(self.result().get("complete", True))

    def test_supported_event_types(self):
        for kind in ("sell", "swap", "spend"):
            with self.subTest(kind=kind):
                self.assertTrue(self.result(type=kind, received="OTHER")["complete"])
        buy = {"type": "buy", "asset": "EXAMPLE", "amount": 1, "date": "2025-01-01",
               "cost_basis_usd": 100, "paid_with_cash": True}
        result = crypto_check.check(crypto_client.normalize(buy), self.skill)
        self.assertTrue(result["complete"])
        self.assertIsNone(result["gain"])
        reward = {"type": "reward", "asset": "EXAMPLE", "amount": 1, "date": "2025-01-01",
                  "fmv_usd": 100, "reward_kind": "staking", "dominion_and_control": True}
        result = crypto_check.check(crypto_client.normalize(reward), self.skill)
        self.assertTrue(result["complete"])
        self.assertEqual(result["income"], Decimal(100))
        reward["reward_kind"] = "hard_fork_airdrop"
        self.assertTrue(crypto_check.check(crypto_client.normalize(reward), self.skill)["complete"])

    def test_cash_and_reward_facts_are_required(self):
        for changes in ({"type": "buy", "paid_with_cash": False},
                        {"type": "buy", "paid_with_cash": None},
                        {"type": "reward", "reward_kind": "staking", "dominion_and_control": False},
                        {"type": "reward", "reward_kind": "unknown", "dominion_and_control": True}):
            with self.subTest(changes=changes):
                self.assertFalse(self.result(**changes)["complete"])

    def test_loss_and_exact_decimal_gain(self):
        result = self.result(proceeds_usd="0.3", cost_basis_usd="0.1")
        self.assertEqual(result["gain"], Decimal("0.2"))
        result = self.result(proceeds_usd="90", date="2024-03-02")
        self.assertEqual(result["term"], "long-term")
        self.assertIn("loss", result["headline"])

    def test_display_ignores_the_callers_decimal_precision(self):
        with localcontext() as context:
            context.prec = 2
            result = self.result(proceeds_usd="123.45", cost_basis_usd="100.00")
        self.assertEqual(result["gain"], Decimal("23.45"))
        self.assertIn("$23.45 gain", result["headline"])

    def test_large_values_are_rounded_once(self):
        value = "999999999999.994999999999999999"
        self.assertIn("$999,999,999,999.99 gain", self.result(proceeds_usd=value, cost_basis_usd=0)["headline"])
        self.assertIn("$999,999,999,999.99 loss", self.result(proceeds_usd=0, cost_basis_usd=value)["headline"])

    def test_unsupported_rules_retain_known_difference(self):
        self.skill["rules"]["long_term_min_days"] = 366
        result = self.result()
        self.assertFalse(result["complete"])
        self.assertEqual(result["gain"], Decimal(10))
        self.assertIsNone(result["term"])

    def test_cash_purchase_cannot_also_be_a_gift(self):
        for method in ("gift", "inheritance", "mining"):
            with self.subTest(method=method), self.assertRaises(ValueError):
                self.result(type="buy", paid_with_cash=True, acquisition_method=method)

    def test_blank_asset_identity_is_incomplete(self):
        self.assertFalse(self.result(asset="   ")["complete"])
        self.assertFalse(self.result(type="swap", received="   ")["complete"])

    def test_extreme_json_decimal_returns_documented_exit_code(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "invalid.json"
            source.write_text('{"amount":1e9999999999999999999}', encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(pipeline.main(["pipeline.py", str(source)]), 2)

    def test_known_term_is_printed_when_gain_is_unknown(self):
        with patch.object(crypto_client, "extract", return_value=[{**self.event, "proceeds_usd": None}]):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertFalse(pipeline.run("unused.json", OAClient(token=None)))
        self.assertIn("holding term: short-term", output.getvalue())

    def test_special_acquisitions_and_leap_day_remain_incomplete(self):
        self.assertFalse(self.result(acquisition_method="gift")["complete"])
        for sold in ("2025-02-28", "2025-03-01"):
            with self.subTest(sold=sold):
                result = self.result(acquire_date="2024-02-29", date=sold)
                self.assertFalse(result["complete"])
                self.assertIsNone(result["term"])

    def test_pipeline_retains_known_gain_and_other_rows(self):
        rows = [{**self.event, "acquire_date": None}, {**self.event, "amount": True}, self.event]
        output = io.StringIO()
        with patch.object(crypto_client, "extract", return_value=rows), contextlib.redirect_stdout(output):
            complete = pipeline.run("unused.json", OAClient(token=None))
        self.assertFalse(complete)
        self.assertIn("Supplied proceeds less basis: $10.00", output.getvalue())
        self.assertIn("invalid input", output.getvalue())
        self.assertIn("short-term, $10.00 gain", output.getvalue())
        self.assertNotIn("signed off", output.getvalue())

    def test_unsupported_lot_array_is_not_ignored(self):
        with self.assertRaisesRegex(ValueError, "separate event"):
            self.result(lots=[{"amount": 1}, {"amount": 2}])

    def test_provider_metadata_is_reported_and_failures_propagate(self):
        oa = OAClient(token="synthetic-test-token")
        reported = {**self.skill, "tier": 1, "verifier": "Example reviewer", "provenance": "verified"}
        with patch.object(oa, "_call", return_value=reported):
            skill = oa.get_skill("us-crypto-tax")
        result = crypto_check.check(crypto_client.normalize(self.event), skill)
        self.assertEqual(result["provenance"], "provider-reported")
        self.assertEqual(result["reported_metadata"]["verifier"], "Example reviewer")
        with patch.object(oa, "_call", side_effect=RuntimeError("synthetic failure")):
            with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
                oa.get_skill("us-crypto-tax")

    def test_incomplete_pipeline_does_not_discard_a_known_term(self):
        with patch.object(crypto_client, "extract", return_value=[{**self.event, "amount": None}]):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertFalse(pipeline.run("unused.json", OAClient(token=None)))
        self.assertIn("holding term: short-term", output.getvalue())


if __name__ == "__main__":
    unittest.main()
