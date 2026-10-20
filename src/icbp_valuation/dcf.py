"""FCFF projection, terminal value, equity bridge, scenarios and the
Excel-replication / reconciliation-bridge routines.

All money in IDR million; per-share values in IDR; shares in millions.
"""
from __future__ import annotations

import copy
from typing import Optional

import numpy as np
import pandas as pd

from .config import historical_table
from .wacc import WaccResult, compute_wacc


# --------------------------------------------------------------------------
# Primitive building blocks (unit-tested)
# --------------------------------------------------------------------------
def fcff(nopat: float, da: float, capex: float, delta_nwc: float) -> float:
    """FCFF = NOPAT + D&A - capex - change in NWC (capex positive = outflow)."""
    return nopat + da - capex - delta_nwc


def present_value(cash_flow: float, rate: float, t: float) -> float:
    """Discount one cash flow received t years from now."""
    return cash_flow / (1.0 + rate) ** t


def pv_of_flows(flows, rate: float) -> float:
    """PV of flows arriving at the end of years 1..N."""
    return float(sum(present_value(cf, rate, t) for t, cf in enumerate(flows, start=1)))


def gordon_terminal_value(fcff_next: float, wacc: float, g: float) -> float:
    """TV at the end of the last explicit year = FCFF_{N+1} / (WACC - g)."""
    if wacc <= g:
        raise ValueError(f"WACC ({wacc:.4%}) must exceed terminal growth ({g:.4%})")
    return fcff_next / (wacc - g)


def exit_multiple_terminal_value(ebitda: float, multiple: float) -> float:
    """TV at the end of the last explicit year = EBITDA_N x EV/EBITDA multiple."""
    return ebitda * multiple


def terminal_fcff_next(nopat: float, da: float, capex: float, nwc_pct: float,
                       revenue: float, g: float) -> float:
    """Normalised FCFF_{N+1}: operating items grow at g, and the NWC build is
    nwc_pct x Revenue_N x g, so reinvestment is consistent with the growth rate."""
    return (nopat + da - capex) * (1.0 + g) - nwc_pct * revenue * g


def implied_growth_from_exit(tv: float, wacc: float, nopat: float, da: float,
                             capex: float, nwc_pct: float, revenue: float) -> float:
    """Perpetual growth g at which the Gordon TV equals `tv` (closed form,
    given the g-dependent normalisation in `terminal_fcff_next`)."""
    a = nopat + da - capex
    b = nwc_pct * revenue
    return (tv * wacc - a) / (tv + a - b)


def equity_bridge(ev: float, h: pd.Series, mode: str = "full") -> dict:
    """Enterprise value -> equity value attributable to ICBP shareholders.

    mode='net_debt_only' : EV - net debt                       (course workbook)
    mode='full'          : EV - net debt - NCI + associates   (book values)
    """
    net_debt = h["net_debt"]
    out = {"ev": ev, "less_net_debt": -net_debt, "less_nci": 0.0, "plus_associates": 0.0}
    equity = ev - net_debt
    if mode == "full":
        out["less_nci"] = -h["non_controlling_equity"]
        out["plus_associates"] = h["long_term_investments"]
        equity += out["less_nci"] + out["plus_associates"]
    elif mode != "net_debt_only":
        raise ValueError(mode)
    out["equity_value"] = equity
    out["per_share"] = equity / h["shares_outstanding_mn"]
    return out


# --------------------------------------------------------------------------
# Course-workbook replication
# --------------------------------------------------------------------------
def _wacc_for(fin: dict, a: dict, h: pd.DataFrame, tax_rate: float) -> WaccResult:
    w = a["wacc"]
    h25 = h.loc[2025]
    return compute_wacc(
        risk_free=w["risk_free"], beta=w["beta"], erp=w["equity_risk_premium"],
        interest_expense=h25["interest_expense"], total_debt=h25["total_debt"],
        tax_rate=tax_rate, share_price=fin["market"]["share_price_idr"],
        shares_mn=h25["shares_outstanding_mn"])


def replicate_workbook(fin: dict, a: dict) -> dict:
    """Re-implement the 'FCFF & DCF' sheet of the course workbook exactly as built."""
    h = historical_table(fin)
    r = a["workbook_replica"]
    nopat = {y: h.loc[y, "ebit"] * (1 - h.loc[y, "effective_tax_rate"]) for y in h.index}
    wc = h["wc_total"]
    dnwc = {2023: wc[2023] - r["nwc_2022_estimate"],
            2024: wc[2024] - wc[2023], 2025: wc[2025] - wc[2024]}
    fc = {y: fcff(nopat[y], h.loc[y, "depreciation_amortization"],
                  h.loc[y, "capex"], dnwc[y]) for y in h.index}
    wr = _wacc_for(fin, a, h, h.loc[2025, "effective_tax_rate"])
    g = r["terminal_growth"]
    fcff_next = fc[2025] * (1 + g)
    firm = gordon_terminal_value(fcff_next, wr.wacc, g)
    eq = equity_bridge(firm, h.loc[2025], r["equity_bridge"])
    price = fin["market"]["share_price_idr"]
    return {
        "nopat": nopat, "delta_nwc": dnwc, "fcff": fc, "wacc_detail": wr,
        "cost_of_equity": wr.cost_of_equity, "pretax_cost_of_debt": wr.pretax_cost_of_debt,
        "after_tax_cost_of_debt": wr.after_tax_cost_of_debt, "market_cap": wr.market_cap,
        "total_debt": wr.total_debt, "weight_equity": wr.weight_equity,
        "weight_debt": wr.weight_debt, "wacc": wr.wacc, "terminal_growth": g,
        "fcff_next": fcff_next, "firm_value": firm, "net_debt": h.loc[2025, "net_debt"],
        "equity_value": eq["equity_value"], "shares_mn": h.loc[2025, "shares_outstanding_mn"],
        "intrinsic_value_per_share": eq["per_share"], "market_price": price,
        "premium_to_price": eq["per_share"] / price - 1,
    }


# --------------------------------------------------------------------------
# Extended model: explicit projection
# --------------------------------------------------------------------------
def project_fcff(h25: pd.Series, drivers: dict, da_pct: float, tax_rate: float) -> pd.DataFrame:
    """Project FY2026E.. using % of revenue drivers. Starts from FY2025 actuals."""
    n = len(drivers["revenue_growth"])
    rows = []
    rev_prev = h25["revenue"]
    nwc_prev = h25["nwc_operating"]
    nwc_pct = drivers["nwc_pct_revenue"]
    base_year = 2025
    for i in range(n):
        rev = rev_prev * (1 + drivers["revenue_growth"][i])
        ebit = rev * drivers["ebit_margin"][i]
        nopat = ebit * (1 - tax_rate)
        da = rev * da_pct
        capex = rev * drivers["capex_pct_revenue"][i]
        nwc = rev * nwc_pct
        dnwc = nwc - nwc_prev
        rows.append({
            "year": base_year + i + 1, "revenue": rev, "growth": drivers["revenue_growth"][i],
            "ebit": ebit, "ebit_margin": drivers["ebit_margin"][i], "nopat": nopat,
            "da": da, "ebitda": ebit + da, "capex": capex, "nwc": nwc, "delta_nwc": dnwc,
            "fcff": fcff(nopat, da, capex, dnwc)})
        rev_prev, nwc_prev = rev, nwc
    return pd.DataFrame(rows).set_index("year")


def value_projection(proj: pd.DataFrame, h25: pd.Series, wacc: float, g: float,
                     nwc_pct: float, exit_multiple: float, price: float,
                     bridge: str = "full") -> dict:
    """Value a projection under a given WACC / g / exit multiple."""
    last = proj.iloc[-1]
    pv_f = pv_of_flows(proj["fcff"].values, wacc)
    n = len(proj)
    f_next = terminal_fcff_next(last["nopat"], last["da"], last["capex"], nwc_pct,
                                last["revenue"], g)
    tv_g = gordon_terminal_value(f_next, wacc, g)
    tv_x = exit_multiple_terminal_value(last["ebitda"], exit_multiple)
    pv_tv_g = present_value(tv_g, wacc, n)
    pv_tv_x = present_value(tv_x, wacc, n)
    out = {"wacc": wacc, "terminal_growth": g, "exit_multiple": exit_multiple,
           "pv_fcff": pv_f, "fcff_next": f_next, "tv_gordon": tv_g, "tv_exit": tv_x,
           "pv_tv_gordon": pv_tv_g, "pv_tv_exit": pv_tv_x}
    for tag, pv_tv in (("gordon", pv_tv_g), ("exit", pv_tv_x)):
        ev = pv_f + pv_tv
        eq = equity_bridge(ev, h25, bridge)
        out[f"ev_{tag}"] = ev
        out[f"equity_{tag}"] = eq["equity_value"]
        out[f"per_share_{tag}"] = eq["per_share"]
        out[f"upside_{tag}"] = eq["per_share"] / price - 1
        out[f"tv_share_{tag}"] = pv_tv / ev
    out["bridge_items"] = equity_bridge(out["ev_gordon"], h25, bridge)
    out["implied_exit_multiple_from_gordon"] = tv_g / last["ebitda"]
    out["implied_g_from_exit"] = implied_growth_from_exit(
        tv_x, wacc, last["nopat"], last["da"], last["capex"], nwc_pct, last["revenue"])
    return out


def headline_per_share(val: dict, method: str, w_gordon: float = 0.5) -> float:
    """Headline value per share: Gordon, exit multiple, or a weighted blend of both."""
    if method == "gordon":
        return val["per_share_gordon"]
    if method == "exit_multiple":
        return val["per_share_exit"]
    if method == "blend":
        return w_gordon * val["per_share_gordon"] + (1 - w_gordon) * val["per_share_exit"]
    raise ValueError(method)


def run_scenario(fin: dict, a: dict, name: str = "base",
                 overrides: Optional[dict] = None) -> dict:
    """Run one scenario of the extended model. `overrides` may replace any driver key
    (e.g. terminal_growth, wacc_adjustment, exit_ev_ebitda) for ad-hoc analysis."""
    h = historical_table(fin)
    h25 = h.loc[2025]
    ext = a["extended"]
    drv = copy.deepcopy(ext["scenarios"][name])
    if overrides:
        drv.update(overrides)
    t = a["wacc"]["statutory_tax_rate"]
    wr = _wacc_for(fin, a, h, t)
    wacc = wr.wacc + drv["wacc_adjustment"]
    proj = project_fcff(h25, drv, ext["da_pct_revenue"], t)
    price = fin["market"]["share_price_idr"]
    val = value_projection(proj, h25, wacc, drv["terminal_growth"], drv["nwc_pct_revenue"],
                           drv["exit_ev_ebitda"], price)
    method = a["valuation"]["headline_terminal_method"]
    per_share = headline_per_share(val, method, a["valuation"].get("blend_weight_gordon", 0.5))
    val.update({"scenario": name, "projection": proj, "wacc_detail": wr,
                "computed_wacc": wr.wacc, "market_price": price,
                "per_share": per_share, "upside": per_share / price - 1,
                "headline_method": method, "drivers": drv})
    return val


def run_all_scenarios(fin: dict, a: dict) -> dict:
    return {s: run_scenario(fin, a, s) for s in a["extended"]["scenarios"]}


def scenario_table(results: dict) -> pd.DataFrame:
    rows = []
    for s, r in results.items():
        rows.append({
            "scenario": s, "WACC": r["wacc"], "g": r["terminal_growth"],
            "exit EV/EBITDA": r["exit_multiple"],
            "EV (Gordon, IDR bn)": r["ev_gordon"] / 1e3,
            "Value/share Gordon (IDR)": r["per_share_gordon"],
            "Value/share exit-mult (IDR)": r["per_share_exit"],
            "Headline value/share (IDR)": r["per_share"],
            "Headline upside vs price": r["upside"],
            "Upside vs price (Gordon)": r["upside_gordon"],
            "Upside vs price (exit-mult)": r["upside_exit"],
            "TV share of EV (Gordon)": r["tv_share_gordon"],
            "Implied exit multiple": r["implied_exit_multiple_from_gordon"],
        })
    return pd.DataFrame(rows).set_index("scenario")


# --------------------------------------------------------------------------
# Sensitivities and reverse DCF
# --------------------------------------------------------------------------
def sensitivity_wacc_g(fin: dict, a: dict, scenario: str = "base") -> pd.DataFrame:
    """Value per share (Gordon TV) over a WACC x terminal-growth grid.
    Rows = WACC, columns = g. Cells with WACC <= g are NaN."""
    base = run_scenario(fin, a, scenario)
    h25 = historical_table(fin).loc[2025]
    waccs = [base["wacc"] + d for d in a["sensitivity"]["wacc_deltas"]]
    gs = a["sensitivity"]["terminal_growth"]
    drv = base["drivers"]
    grid = pd.DataFrame(index=pd.Index(waccs, name="WACC"), columns=pd.Index(gs, name="g"),
                        dtype=float)
    for w in waccs:
        for g in gs:
            if w <= g:
                grid.loc[w, g] = np.nan
                continue
            v = value_projection(base["projection"], h25, w, g, drv["nwc_pct_revenue"],
                                 drv["exit_ev_ebitda"], base["market_price"])
            grid.loc[w, g] = v["per_share_gordon"]
    return grid


def sensitivity_wacc_exit(fin: dict, a: dict, scenario: str = "base") -> pd.DataFrame:
    """Value per share (exit-multiple TV) over a WACC x exit-multiple grid."""
    base = run_scenario(fin, a, scenario)
    h25 = historical_table(fin).loc[2025]
    waccs = [base["wacc"] + d for d in a["sensitivity"]["wacc_deltas"]]
    ms = a["sensitivity"]["exit_multiples"]
    drv = base["drivers"]
    grid = pd.DataFrame(index=pd.Index(waccs, name="WACC"),
                        columns=pd.Index(ms, name="EV/EBITDA"), dtype=float)
    for w in waccs:
        for m in ms:
            v = value_projection(base["projection"], h25, w, drv["terminal_growth"],
                                 drv["nwc_pct_revenue"], m, base["market_price"])
            grid.loc[w, m] = v["per_share_exit"]
    return grid


def implied_wacc(fin: dict, a: dict, scenario: str = "base", method: str = "gordon",
                 lo: Optional[float] = None, hi: float = 0.40, tol: float = 1e-10) -> float:
    """Reverse DCF: the WACC at which the model value per share equals the market price."""
    base = run_scenario(fin, a, scenario)
    h25 = historical_table(fin).loc[2025]
    drv = base["drivers"]
    price = base["market_price"]
    g = drv["terminal_growth"]
    lo = (g + 1e-4) if lo is None else lo
    key = "per_share_gordon" if method == "gordon" else "per_share_exit"

    def f(w):
        v = value_projection(base["projection"], h25, w, g, drv["nwc_pct_revenue"],
                             drv["exit_ev_ebitda"], price)
        return v[key] - price

    if f(lo) < 0 or f(hi) > 0:
        raise ValueError("price not bracketed by the search interval")
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def market_implied_ev_ebitda(fin: dict) -> float:
    """EV at market (mkt cap + debt - cash/ST inv + NCI - associates) / FY2025 EBITDA."""
    h25 = historical_table(fin).loc[2025]
    mcap = fin["market"]["share_price_idr"] * h25["shares_outstanding_mn"]
    ev = (mcap + h25["total_debt"] - h25["cash_and_st_investments"]
          + h25["non_controlling_equity"] - h25["long_term_investments"])
    return ev / h25["ebitda"]


# --------------------------------------------------------------------------
# Reconciliation: Excel as-built  ->  extended base case
# --------------------------------------------------------------------------
def bridge_walk(fin: dict, a: dict) -> pd.DataFrame:
    """Step-by-step walk from the workbook's value per share to the extended base case.
    Each step changes ONE thing; the order is a presentation choice (effects interact)."""
    h = historical_table(fin)
    h25 = h.loc[2025]
    rep = replicate_workbook(fin, a)
    wacc = rep["wacc"]
    g_x = rep["terminal_growth"]
    price = fin["market"]["share_price_idr"]
    nopat25 = rep["nopat"][2025]
    da, capex = h25["depreciation_amortization"], h25["capex"]

    steps = [("0. Excel as built (workbook)", rep["intrinsic_value_per_share"])]

    dnwc_op = h.loc[2025, "nwc_operating"] - h.loc[2024, "nwc_operating"]
    f_op = fcff(nopat25, da, capex, dnwc_op)
    ev1 = gordon_terminal_value(f_op * (1 + g_x), wacc, g_x)
    steps.append(("1. NWC excludes cash, ST investments and debt",
                  equity_bridge(ev1, h25, "net_debt_only")["per_share"]))
    steps.append(("2. Equity bridge: less NCI, plus associates",
                  equity_bridge(ev1, h25, "full")["per_share"]))
    g_b = a["extended"]["scenarios"]["base"]["terminal_growth"]
    ev3 = gordon_terminal_value(f_op * (1 + g_b), wacc, g_b)
    steps.append((f"3. Terminal growth {g_x:.0%} -> {g_b:.1%}",
                  equity_bridge(ev3, h25, "full")["per_share"]))
    base = run_scenario(fin, a, "base")
    no_adj = run_scenario(fin, a, "base", {"wacc_adjustment": 0.0})
    steps.append(("4. 5-yr explicit projection, normalised terminal, 22% tax",
                  no_adj["per_share_gordon"]))
    adj = a["extended"]["scenarios"]["base"]["wacc_adjustment"]
    steps.append((f"5. Discount-rate realism adjustment (+{adj*100:.1f}pp on WACC)",
                  base["per_share_gordon"]))
    steps.append(("6. Headline = blend of Gordon and exit-multiple TV", base["per_share"]))
    df = pd.DataFrame(steps, columns=["step", "value_per_share"])
    df["change"] = df["value_per_share"].diff()
    df["vs_price"] = df["value_per_share"] / price - 1
    return df
