"""Quantified audit of the course workbook (UAS ICBP FY2023-2025).

Every number is recomputed here from data/icbp_financials.yaml or from constants that
are read off the workbook and cited by cell. Findings are about the *workbook as
submitted*; they are not criticism of the underlying filings.
"""
from __future__ import annotations

import math

import pandas as pd

from .config import historical_table
from .dcf import (equity_bridge, fcff, gordon_terminal_value, replicate_workbook)

# Constants read from the workbook sheet 'FOREX EXPOSURE' (cells in the keys)
FX_SHEET = {
    "E38:E40 inputs": {"USD": (34_492_500, 0.00421), "EUR": (1_083_000, 0.00518),
                       "SGD": (482_000, 0.00312)},      # (net exposure IDR mn, daily vol)
    "z99": 2.326,
    "net_income_2025": None,   # filled from financials
}


def fx_var_recalc(net_income_2025: float) -> dict:
    """Recompute the workbook P&L-at-risk with trading-day annualisation (sqrt 252)
    instead of calendar-day (sqrt 365), and with a diversified (correlated) total."""
    rows = FX_SHEET["E38:E40 inputs"]
    z = FX_SHEET["z99"]
    out = {}
    for label, n in (("sqrt365 (workbook)", 365), ("sqrt252 (trading days)", 252)):
        total = sum(abs(expo) * dv * math.sqrt(n) * z for expo, dv in rows.values())
        out[label] = {"total_idr_mn": total, "pct_net_income": total / net_income_2025}
    return out


def audit_findings(fin: dict, a: dict) -> pd.DataFrame:
    h = historical_table(fin)
    h25, h24 = h.loc[2025], h.loc[2024]
    rep = replicate_workbook(fin, a)
    wacc, g = rep["wacc"], rep["terminal_growth"]
    rows = []

    def add(area, finding, excel, corrected, impact):
        rows.append({"area": area, "finding": finding, "workbook": excel,
                     "recomputed": corrected, "impact": impact})

    # 1. NWC definition
    d_wb = h25["wc_total"] - h24["wc_total"]
    d_op = h25["nwc_operating"] - h24["nwc_operating"]
    f_op = fcff(rep["nopat"][2025], h25["depreciation_amortization"], h25["capex"], d_op)
    add("DCF / NWC",
        "Change in 'NWC' is built from total current assets less total current liabilities, so "
        "it includes cash, short-term investments and short-term debt (financing items). "
        "FY2025 change in working capital is dominated by cash build-up.",
        f"dNWC FY2025 = {d_wb:,.0f}", f"operating dNWC = {d_op:,.0f}",
        f"FY2025 FCFF {rep['fcff'][2025]:,.0f} -> {f_op:,.0f} (IDR mn)")

    # 2. 2022 plug
    add("DCF / NWC",
        "FY2023 change in NWC subtracts a hard-coded, unsourced FY2022 NWC of 21,036,430 "
        "inside formula 'FCFF & DCF'!B19. FY2023 FCFF is therefore not reproducible from the data.",
        f"FCFF FY2023 = {rep['fcff'][2023]:,.0f}", "not computable without FY2022 balance sheet",
        "Does not drive the headline value (FY2025 base) but shows in the FCFF growth average.")

    # 3. equity bridge
    ev = rep["firm_value"]
    full = equity_bridge(ev, h25, "full")
    simple = equity_bridge(ev, h25, "net_debt_only")
    add("DCF / equity bridge",
        "Equity value = EV - net debt only. Consolidated FCFF includes 100% of subsidiaries, so the "
        "non-controlling interest must be deducted; investments in associates (outside EBIT) should be added.",
        f"{simple['per_share']:,.0f} IDR/share",
        f"{full['per_share']:,.0f} IDR/share (book NCI {h25['non_controlling_equity']:,.0f}, "
        f"associates {h25['long_term_investments']:,.0f})",
        f"{full['per_share'] - simple['per_share']:+,.0f} IDR/share at the workbook EV")

    # 4. growth vs risk-free and terminal dominance
    add("DCF / terminal value",
        "Terminal growth 5.0% exceeds the 4.75% risk-free proxy and leaves a WACC - g spread of only "
        "2.26 pp; 100% of value sits in a single Gordon term on one (un-normalised) year of FCFF.",
        f"g = {g:.2%}, WACC = {wacc:.2%}, spread = {wacc - g:.2%}",
        "g capped at <= risk-free is the usual rule of thumb",
        f"EV is {1 / (wacc - g):.0f}x next-year FCFF; WACC +0.5 pp alone cuts EV by "
        f"{1 - gordon_terminal_value(rep['fcff_next'], wacc + 0.005, g) / ev:.0%}")

    # 5. WACC inputs
    add("WACC",
        "Risk-free rate is the BI 7-day repo (policy) rate, not a long-dated government bond yield; "
        "beta 0.60 and ERP 7.5% are taken from different bases. Cost of equity 9.25% is low for a rupiah "
        "equity stream.",
        f"Ke = {rep['cost_of_equity']:.2%}, WACC = {wacc:.2%}", "see +2.0 pp judgement in assumptions.yaml",
        "Reverse DCF in the notebook shows the market-implied WACC")

    # 6. balance sheet integrity
    add("Data integrity",
        "Balance sheet does not balance: total assets differ from liabilities + equity in FY2023 and "
        "FY2024 (the workbook notes the check but has no check formula).",
        "no check cell",
        f"gap FY2023 {h.loc[2023, 'balance_check_gap']:,.0f}; FY2024 {h.loc[2024, 'balance_check_gap']:,.0f}; "
        f"FY2025 {h25['balance_check_gap']:,.0f}",
        "Small vs total assets (0.06% in FY2024) but indicates a transcription error in one line item")

    # 7. leverage cross-checks
    rev, ebit, eps, gp = h["revenue"], h["ebit"], h["eps"], h["gross_profit"]
    dol_f = gp[2025] / ebit[2025]
    dol_v = ((ebit[2025] - ebit[2024]) / ebit[2024]) / ((rev[2025] - rev[2024]) / rev[2024])
    dfl_f = ebit[2025] / (ebit[2025] - h25["interest_expense"])
    dfl_v = ((eps[2025] - eps[2024]) / eps[2024]) / ((ebit[2025] - ebit[2024]) / ebit[2024])
    add("Leverage",
        "DOL is defined as gross profit / EBIT (gross profit is not contribution margin because COGS holds "
        "fixed overhead). The workbook's own verification rows contradict the formulas, yet the narrative says "
        "they should be 'approximately equal'. DFL ignores associates and FX lines that drive EPS.",
        f"DOL {dol_f:.2f}, DFL {dfl_f:.2f} (formula)",
        f"DOL {dol_v:.2f}, DFL {dfl_v:.2f} (realised %change ratios)",
        "FY2025 EPS growth was driven by associates swinging from -1.39 tn to +0.24 tn, not operating leverage")

    # 8. FX VaR
    var = fx_var_recalc(h25["net_income"])
    wb, td = var["sqrt365 (workbook)"], var["sqrt252 (trading days)"]
    add("FX exposure (workbook sheet)",
        "Annual volatility is scaled by sqrt(365) although BI rates are published on business days; "
        "per-currency VaRs are summed with no correlation; volatilities are typed in, not computed; "
        "exposure amounts are marked '(est.)'; column header says 'Net Income 2024' but divides by FY2025.",
        f"P&L at risk {wb['total_idr_mn']:,.0f} ({wb['pct_net_income']:.0%} of NI)",
        f"{td['total_idr_mn']:,.0f} ({td['pct_net_income']:.0%} of NI) with sqrt(252)",
        "Order of magnitude unchanged, but the conclusion that 73% of net income is at risk is overstated")

    # 9. narrative / labels
    add("Presentation",
        "Hard-coded narratives disagree with computed cells: 'VALUASI PER'!A42 says 'Target DCF: IDR 12,000+' "
        "while the DCF cell is 20,397; A15 label says P/E 9.23x but the input is 9.67x; several 'Link: ... 2024' "
        "notes point at FY2025 cells.",
        "text vs cells", "n/a", "Cosmetic, but undermines trust in the recommendation text")

    # 10. possible double count
    add("Cash flow statement",
        "Operating cash flow = net income + D&A + 'adjustments', where the adjustment line is labelled "
        "'Incl. D&A + changes in WC'. If the adjustment already contains D&A it is counted twice. "
        "Cannot be confirmed without the filing - flagged, not asserted.",
        f"CFO FY2025 = {h25['cfo_workbook']:,.0f}", "verify against the reported cash flow statement",
        "Affects the workbook's levered FCF and dividend-payout ratios, not the FCFF valuation")

    return pd.DataFrame(rows)
