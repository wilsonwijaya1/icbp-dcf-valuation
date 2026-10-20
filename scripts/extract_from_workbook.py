"""Extract hard-coded inputs and Excel-computed reference values from the
original course workbook (UAS ICBP FY2023-2025).

The workbook itself is NOT stored in this repository (its file name and cover
sheet carry personal/course identifiers). This script regenerates:

  data/icbp_financials.yaml    - hard-coded financial-statement inputs (IDR million)
  data/excel_reference.json    - cached values Excel computed, with cell addresses

Usage:  python scripts/extract_from_workbook.py <path-to-workbook.xlsx>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import openpyxl
import yaml

ROOT = Path(__file__).resolve().parents[1]

# (key, row) in sheet 'LAPORAN KEUANGAN'; columns B,C,D = FY2023, FY2024, FY2025
IS_ROWS = {
    "revenue": 7, "cogs": 8, "selling_general_admin": 9, "other_operating_income": 10,
    "interest_expense": 11, "interest_and_investment_income": 12,
    "share_of_associates": 13, "fx_gain_loss": 14, "income_tax": 15,
    "non_controlling_interest": 16, "depreciation_amortization": 17,
    "shares_outstanding_mn": 18,
}
BS_ROWS = {
    "cash": 33, "short_term_investments": 34, "receivables": 35, "inventories": 36,
    "other_current_assets": 37, "ppe_net": 38, "long_term_investments": 39,
    "goodwill": 40, "other_intangibles": 41, "other_noncurrent_assets": 42,
    "trade_payables": 43, "short_term_debt": 44, "current_portion_ltd": 45,
    "other_current_liabilities": 46, "long_term_debt": 47,
    "other_long_term_liabilities": 48, "equity_parent": 49, "non_controlling_equity": 50,
}
CF_ROWS = {
    "noncash_and_wc_adjustments": 65, "capex": 66, "ppe_disposal_proceeds": 67,
    "other_investing": 68, "net_debt_proceeds": 69, "dividends_paid": 70,
    "other_financing": 71, "fx_effect_on_cash": 72,
}
YEARS = {"B": 2023, "C": 2024, "D": 2025}


def main(path: str) -> None:
    wb_v = openpyxl.load_workbook(path, data_only=True)
    wb_f = openpyxl.load_workbook(path)
    lk = wb_v["LAPORAN KEUANGAN"]

    def block(rows: dict[str, int]) -> dict[str, dict[int, float]]:
        return {k: {YEARS[c]: lk[f"{c}{r}"].value for c in YEARS} for k, r in rows.items()}

    fin = {
        "meta": {
            "company": "PT Indofood CBP Sukses Makmur Tbk",
            "ticker": "ICBP (IDX)",
            "currency_unit": "IDR million, except per-share data",
            "fiscal_year_end": "31 December",
            "source": "ICBP annual reports / IDX filings",
            "provenance_note": (
                "Figures are transcribed from a university Financial Management "
                "workbook whose stated sources are the ICBP annual reports / IDX "
                "filings (indofoodcbp.com), S&P Global MI via stockanalysis.com, "
                "and Yahoo Finance. They have not been re-audited against the "
                "original filings by the repository author."
            ),
        },
        "income_statement": block(IS_ROWS),
        "balance_sheet": block(BS_ROWS),
        "cash_flow": block(CF_ROWS),
        "market": {
            "analysis_date": "May 2026 (as recorded in the workbook)",
            "share_price_idr": wb_v["FCFF & DCF"]["B40"].value,
            "pe_trailing": wb_v["VALUASI PER"]["B8"].value,
            "ev_ebitda_market_quoted": wb_v["VALUASI PER"]["B26"].value,
        },
        "workbook_hardcodes": {
            "nwc_2022_estimate_in_formula_B19": 21036430,
            "note": "Hard-coded inside formula 'FCFF & DCF'!B19; no source given.",
        },
    }
    out = ROOT / "data" / "icbp_financials.yaml"
    out.write_text(yaml.safe_dump(fin, sort_keys=False, allow_unicode=True), encoding="utf-8")

    # Reference values (cached results computed by Excel) for the DCF sheet
    dcf = wb_v["FCFF & DCF"]
    ref_cells = {
        "nopat": {"2023": "B18", "2024": "C18", "2025": "D18"},
        "delta_nwc": {"2023": "B19", "2024": "C19", "2025": "D19"},
        "fcff": {"2023": "B20", "2024": "C20", "2025": "D20"},
        "cost_of_equity": "B30", "pretax_cost_of_debt": "B35",
        "after_tax_cost_of_debt": "B37", "market_cap": "B41", "total_debt": "B42",
        "weight_equity": "B44", "weight_debt": "B45", "wacc": "B46",
        "terminal_growth": "B50", "fcff_next": "B52", "firm_value": "B54",
        "net_debt": "B55", "equity_value": "B56", "shares_mn": "B57",
        "intrinsic_value_per_share": "B58", "market_price": "B59",
        "premium_to_price": "B60",
    }

    def fetch(spec):
        if isinstance(spec, dict):
            return {k: dcf[v].value for k, v in spec.items()}
        return dcf[spec].value

    ref = {"sheet": "FCFF & DCF", "cells": ref_cells,
           "values": {k: fetch(v) for k, v in ref_cells.items()},
           "formulas": {k: (dcf[v].value if not isinstance(v, dict) else
                            {a: dcf[b].value for a, b in v.items()})
                        for k, v in ref_cells.items()}}
    # The formulas dict is informational (shows how Excel built each number)
    lk_ref = {
        "ebit": {YEARS[c]: lk[f"{c}20"].value for c in YEARS},
        "effective_tax_rate": {YEARS[c]: lk[f"{c}26"].value for c in YEARS},
        "net_income": {YEARS[c]: lk[f"{c}23"].value for c in YEARS},
        "ebitda": {YEARS[c]: lk[f"{c}24"].value for c in YEARS},
        "nwc_total_working_capital": {YEARS[c]: lk[f"{c}62"].value for c in YEARS},
        "net_debt": {YEARS[c]: lk[f"{c}61"].value for c in YEARS},
        "total_assets": {YEARS[c]: lk[f"{c}53"].value for c in YEARS},
        "total_liab_plus_equity": {YEARS[c]: lk[f"{c}58"].value for c in YEARS},
    }
    ref["lk_sheet_reference"] = lk_ref
    (ROOT / "data" / "excel_reference.json").write_text(
        json.dumps(ref, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    print("wrote data/icbp_financials.yaml and data/excel_reference.json")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
