"""Loading of assumptions.yaml and the historical financial data."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
YEARS = (2023, 2024, 2025)


def load_assumptions(path: str | Path | None = None) -> dict:
    path = Path(path) if path else PROJECT_ROOT / "assumptions.yaml"
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_financials(path: str | Path | None = None) -> dict:
    path = Path(path) if path else PROJECT_ROOT / "data" / "icbp_financials.yaml"
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def historical_table(fin: dict) -> pd.DataFrame:
    """Return a year-indexed DataFrame of statement lines and derived metrics.

    Derived lines reproduce the formulas of the course workbook's
    'LAPORAN KEUANGAN' sheet (rows 19-30, 51-62, 73-78) so they can be audited.
    """
    inc, bs, cf = fin["income_statement"], fin["balance_sheet"], fin["cash_flow"]
    rows = {}
    for y in YEARS:
        r = {}
        for block in (inc, bs, cf):
            for k, series in block.items():
                r[k] = float(series[y])
        r["gross_profit"] = r["revenue"] - r["cogs"]
        r["ebit"] = r["gross_profit"] - r["selling_general_admin"] + r["other_operating_income"]
        r["ebt"] = (r["ebit"] - r["interest_expense"] + r["interest_and_investment_income"]
                    + r["share_of_associates"] + r["fx_gain_loss"])
        r["profit_after_tax"] = r["ebt"] - r["income_tax"]
        r["net_income"] = r["profit_after_tax"] - r["non_controlling_interest"]
        r["ebitda"] = r["ebit"] + r["depreciation_amortization"]
        r["eps"] = r["net_income"] / r["shares_outstanding_mn"]
        r["effective_tax_rate"] = r["income_tax"] / r["ebt"]
        r["ebit_margin"] = r["ebit"] / r["revenue"]
        # balance sheet aggregates
        r["current_assets"] = (r["cash"] + r["short_term_investments"] + r["receivables"]
                               + r["inventories"] + r["other_current_assets"])
        r["noncurrent_assets"] = (r["ppe_net"] + r["long_term_investments"] + r["goodwill"]
                                  + r["other_intangibles"] + r["other_noncurrent_assets"])
        r["total_assets"] = r["current_assets"] + r["noncurrent_assets"]
        r["current_liabilities"] = (r["trade_payables"] + r["short_term_debt"]
                                    + r["current_portion_ltd"] + r["other_current_liabilities"])
        r["total_liabilities"] = (r["current_liabilities"] + r["long_term_debt"]
                                  + r["other_long_term_liabilities"])
        r["total_equity"] = r["equity_parent"] + r["non_controlling_equity"]
        r["total_liab_and_equity"] = r["total_liabilities"] + r["total_equity"]
        r["balance_check_gap"] = r["total_assets"] - r["total_liab_and_equity"]
        r["total_debt"] = r["short_term_debt"] + r["current_portion_ltd"] + r["long_term_debt"]
        r["cash_and_st_investments"] = r["cash"] + r["short_term_investments"]
        r["net_debt"] = r["total_debt"] - r["cash_and_st_investments"]
        # two competing definitions of net working capital
        r["wc_total"] = r["current_assets"] - r["current_liabilities"]        # workbook (incl. cash & debt)
        r["nwc_operating"] = (r["receivables"] + r["inventories"] + r["other_current_assets"]
                              - r["trade_payables"] - r["other_current_liabilities"])
        # workbook cash-flow lines
        r["cfo_workbook"] = r["net_income"] + r["depreciation_amortization"] + r["noncash_and_wc_adjustments"]
        r["fcf_workbook"] = r["cfo_workbook"] - r["capex"]
        rows[y] = r
    return pd.DataFrame(rows).T
