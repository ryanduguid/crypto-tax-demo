# crypto → OpenAccountants: illustrative event calculations

Read a documented JSON event format and calculate supplied proceeds less basis,
a supported holding period or a supported reward receipt. The bundled rules are
unverified examples. The output does not establish professional sign-off or an
exact tax liability.

![Illustrative crypto calculations](demo.svg)

## Run it

Python 3.10 or later and the standard library are sufficient.

```bash
python pipeline.py
python pipeline.py samples/transactions.json
python -m unittest discover -s tests -v
python make_svg.py
```

The default command and SVG generator always use the bundled examples.
Empty, incomplete or invalid input returns exit code 2. Valid rows remain visible when
another row is incomplete or invalid. No exchange, wallet, CSV, Rotki or
Etherscan adapter is included. The five sample records are independent examples,
not a reconciled portfolio or inventory ledger.

## Supported facts and calculations

The example assumes a US individual using the cash method, holding ordinary
investment property. It does not calculate filing obligations, net tax, tax
rates, lot selection, income thresholds or special holding-period adjustments.

| Event | Required facts beyond asset, amount and event date | Result |
|---|---|---|
| `buy` | `paid_with_cash: true`, supplied adjusted `cost_basis_usd` | Cash acquisition with no disposal gain in this example |
| `sell`, `swap`, `spend` | Supplied `proceeds_usd`, adjusted `cost_basis_usd`, `acquire_date`, `acquisition_method: "purchase"` | Gain or loss and a supported holding term |
| `swap` | The disposal facts above and `received` or `asset_in` | Disposal of the outgoing asset |
| `reward` | `reward_kind: "staking"` or `"hard_fork_airdrop"`, `dominion_and_control: true`, supplied fair market value | Illustrative ordinary income on the date control was obtained |

Supply one acquisition lot per disposal record. Proceeds and adjusted basis
must already include applicable fee adjustments; the demo does not calculate
fees or basis. Gifts, inheritance, transfers, loans, derivatives and multiple
lots within one record are outside the supported calculation.

Gain equals proceeds less basis using decimal arithmetic. Explicit zero values
remain zero; absent values remain unknown. A missing date can leave that value
difference known while the holding term remains unresolved. A zero result is
reported as no gain or loss.

## Holding period and sources

The term uses more than a calendar year, following the general rule in
[IRS Publication 550](https://www.irs.gov/publications/p550#en_US_2025_publink100010540).
A purchase on 1 March 2023 followed by a sale on 1 March 2024 is short-term
despite spanning 366 days. A sale on 2 March 2024 is long-term under the
ordinary-purchase assumptions.

29 February acquisitions remain incomplete because their calendar boundary has
not been independently verified for this demo. Missing dates and unsupported
acquisition methods also remain incomplete. Impossible or reversed dates are
invalid; none defaults to short-term.

The supported reward assumptions follow the IRS guidance on
[staking validation rewards](https://www.irs.gov/irb/2023-33_IRB#REV-RUL-2023-14)
and [hard-fork airdrops](https://www.irs.gov/individuals/international-taxpayers/frequently-asked-questions-on-virtual-currency-transactions).
A generic reward label or ledger timestamp alone does not prove receipt or
control. Other airdrop types remain unsupported.

## JSON contract

- Use `YYYY-MM-DD` dates and explicit JSON Booleans. Strings such as
  `"false"` and numeric Boolean substitutes are rejected.
- Amounts, proceeds and basis accept numeric JSON values or decimal strings.
  Values must be finite, non-negative, at most `1e12` and have no more than
  18 decimal places. The calculation uses 50 digits of precision.
- Monetary fields are USD values. Display rounds to cents using half-up
  rounding; stored gain retains the exact difference.
- Supported aliases are `asset_out` for `asset`, `amount_out` for `amount`,
  `asset_in` for `received` and `fmv_usd` for `proceeds_usd`.
  Text fields are trimmed. Conflicting aliases are rejected, including explicit
  zero or null versus a populated alternate value.
- Unknown event types and incompatible loaded rule contracts remain incomplete.
  A supplied `is_disposal` flag must agree with the recognised event type.

## Optional live adapter

`python pipeline.py --live` opts into the experimental JSON-RPC adapter and
requires `OA_MCP_TOKEN` configured outside the repository. The live
authentication and response contract have not been verified. Failed live calls
never fall back to bundled rules.

The supported rule contract is the `ordinary-us-crypto-v1` dictionary in
`oa_client.py`. A legacy `long_term_min_days` rule is incompatible with calendar
classification. Provider tier, verifier and source metadata remain reported
information, not independent attestation.

## Files

| File | Role |
|---|---|
| `pipeline.py` | CLI and complete, incomplete or invalid result reporting |
| `crypto_client.py` | JSON extraction and normalisation |
| `crypto_check.py` | Supported event calculations and calendar classification |
| `oa_client.py` | Bundled rules and experimental live adapter |
| `samples/transactions.json` | Five fabricated events |
| `tests/` | Offline calculation, adapter and command-line regressions |
