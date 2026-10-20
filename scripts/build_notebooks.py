"""Build the two notebooks from source cells, then execute them with nbconvert:

    python scripts/build_notebooks.py

Keeping the notebooks generated from a script keeps diffs reviewable; the committed
.ipynb files are the executed versions.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]


def md(text):
    return nbf.v4.new_markdown_cell(text.strip("\n"))


def code(text):
    return nbf.v4.new_code_cell(text.strip("\n"))


SETUP = '''
import sys
from pathlib import Path
ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
from IPython.display import Image, display

from icbp_valuation import load_assumptions, load_financials
from icbp_valuation import plots

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 30)
fin, a = load_financials(), load_assumptions()
price = fin["market"]["share_price_idr"]
'''


def dcf_notebook() -> nbf.NotebookNode:
    nb = nbf.v4.new_notebook()
    c = nb.cells
    c.append(md("""
# ICBP (PT Indofood CBP Sukses Makmur Tbk) - DCF valuation, rebuilt in Python

> **Educational analysis, not investment advice.** Originally a university Financial Management
> assignment; rebuilt and extended in Python.

**What this notebook does**

1. Loads the FY2023-FY2025 financials and every assumption from `data/` and `assumptions.yaml`.
2. Re-implements the course Excel workbook and checks that the Python result matches it.
3. Audits the workbook (formula and modelling issues) with numbers.
4. Builds an extended model: 5-year FCFF projection, WACC, Gordon-growth and exit-multiple terminal values,
   bull/base/bear scenarios, WACC x g heat maps and a reverse DCF.

**Data provenance.** Statement figures are the ones used in the course workbook, whose stated sources are the
ICBP annual reports / IDX filings (plus S&P Global MI via stockanalysis.com and Yahoo Finance). They were
transcribed from that workbook and not re-audited against the filings by the repository author.
The market price (IDR 7,650) is the price recorded in the workbook for May 2026.
"""))
    c.append(code(SETUP))
    c.append(md("## 1. Historical financials (IDR million)"))
    c.append(code('''
from icbp_valuation.config import historical_table
h = historical_table(fin)
cols = ["revenue", "gross_profit", "ebit", "ebitda", "net_income", "eps", "effective_tax_rate",
        "ebit_margin", "capex", "depreciation_amortization", "total_debt", "cash_and_st_investments",
        "net_debt", "nwc_operating", "wc_total"]
display(h[cols].T.style.format("{:,.3f}", subset=pd.IndexSlice[["effective_tax_rate", "ebit_margin"], :])
        .format("{:,.0f}", subset=pd.IndexSlice[[c for c in cols if c not in ("effective_tax_rate", "ebit_margin", "eps")], :])
        .format("{:,.1f}", subset=pd.IndexSlice[["eps"], :]))
'''))
    c.append(md("""
## 2. Verification: Python replica vs the Excel workbook

`replicate_workbook` re-implements the sheet *FCFF & DCF* **exactly as built** (including its questionable choices,
listed in section 3). Each output is compared with the value Excel cached in the original file
(`data/excel_reference.json`, with cell addresses).
"""))
    c.append(code('''
from icbp_valuation.verify import compare
cmp = compare(fin, a)
print(f"{cmp['match'].sum()} of {len(cmp)} items match within relative tolerance {a['verification']['relative_tolerance']:.0e}")
print(f"Worst relative difference: {cmp['rel_diff'].max():.2e}")
show = cmp[cmp["item"].isin(["fcff 2025", "wacc", "firm_value", "equity_value", "intrinsic_value_per_share"])]
display(show.style.format({"python": "{:,.6f}", "excel": "{:,.6f}", "abs_diff": "{:.2e}", "rel_diff": "{:.1e}"}))
'''))
    c.append(md("""
The replica reproduces Excel to floating-point precision (differences of about 1e-9 IDR come from Excel's cached
values being stored with ~15 significant digits). The workbook's headline - **IDR 20,397 per share, +167% vs the
IDR 7,650 price** - is therefore *correctly computed from its own assumptions*. The problems are in the
assumptions and structure, not the arithmetic.
"""))
    c.append(md("## 3. Audit of the workbook"))
    c.append(code('''
from icbp_valuation.audit import audit_findings
aud = audit_findings(fin, a)
pd.set_option("display.max_colwidth", 400)
for i, r in aud.iterrows():
    print(f"[{i+1}] {r.area}\\n    Finding : {r.finding}\\n    Workbook: {r.workbook}\\n    Recomputed: {r.recomputed}\\n    Impact  : {r.impact}\\n")
'''))
    c.append(md("""
Two of these matter most for the valuation: (1) the change in "NWC" includes cash and debt, which *understates*
FCFF (FY2025: 5.47 tn in the workbook vs 9.04 tn with operating NWC), and (2) a 5% perpetual growth rate against a
7.26% WACC makes the value extremely fragile. They push in opposite directions, which is why the walk in
section 8 is informative.
"""))
    c.append(md("## 4. Cost of capital (CAPM)"))
    c.append(code('''
from icbp_valuation.dcf import run_scenario, replicate_workbook
rep = replicate_workbook(fin, a)
base = run_scenario(fin, a, "base")
w = base["wacc_detail"]
pd.DataFrame({
    "Workbook (effective tax)": [rep["wacc_detail"].risk_free, rep["wacc_detail"].beta, rep["wacc_detail"].erp,
                                 rep["cost_of_equity"], rep["pretax_cost_of_debt"], rep["wacc_detail"].tax_rate,
                                 rep["after_tax_cost_of_debt"], rep["weight_equity"], rep["weight_debt"], rep["wacc"]],
    "Extended (22% statutory)": [w.risk_free, w.beta, w.erp, w.cost_of_equity, w.pretax_cost_of_debt, w.tax_rate,
                                 w.after_tax_cost_of_debt, w.weight_equity, w.weight_debt, w.wacc],
}, index=["Risk-free (BI repo)", "Beta", "ERP", "Cost of equity", "Pre-tax cost of debt", "Tax rate",
          "After-tax cost of debt", "Weight equity (market)", "Weight debt (book)", "WACC"]).style.format("{:.4f}")
'''))
    c.append(md("""
Extended base case adds a **+2.0 pp judgement** to the computed WACC (`wacc_adjustment` in `assumptions.yaml`).
Reason: the risk-free proxy is a policy rate and beta 0.60 is low, so 7.3% is thin for a rupiah cash-flow stream.
This is an assumption, not a fact - set it to 0 to see the workbook-consistent discount rate, and see the heat maps
for the full range.
"""))
    c.append(md("## 5. FCFF projection (base case)"))
    c.append(code('''
proj = base["projection"].copy()
display((proj / 1e3).rename(columns={"revenue": "Revenue", "ebit": "EBIT", "nopat": "NOPAT", "da": "D&A",
        "ebitda": "EBITDA", "capex": "Capex", "nwc": "Operating NWC", "delta_nwc": "dNWC", "fcff": "FCFF"})
        [["Revenue", "EBIT", "NOPAT", "D&A", "Capex", "dNWC", "FCFF", "EBITDA"]].style.format("{:,.0f}")
        .set_caption("IDR billion"))
display(Image(plots.plot_fcff(fin, a, base)))
'''))
    c.append(md("## 6. Valuation: Gordon growth and exit multiple, by scenario"))
    c.append(code('''
from icbp_valuation.dcf import run_all_scenarios, scenario_table, market_implied_ev_ebitda
res = run_all_scenarios(fin, a)
st = scenario_table(res)
pct = ["WACC", "g", "Upside vs price (Gordon)", "Upside vs price (exit-mult)", "Headline upside vs price", "TV share of EV (Gordon)"]
display(st.T.style.format("{:,.0f}").format("{:.1%}", subset=pd.IndexSlice[pct, :])
        .format("{:.1f}x", subset=pd.IndexSlice[["exit EV/EBITDA", "Implied exit multiple"], :]))
print(f"Market price: IDR {price:,.0f}   |   market-implied EV/EBITDA (incl. NCI, less associates): {market_implied_ev_ebitda(fin):.2f}x")
display(Image(plots.plot_scenarios(res, price)))
'''))
    c.append(md("""
**Reading the numbers.** The Gordon-growth value is far above the exit-multiple value in every scenario. The reason is
visible in the "Implied exit multiple" row: the Gordon terminal value is equivalent to 9-18x EBITDA, while ICBP
trades at about 7x. The headline is therefore a 50/50 blend (`blend_weight_gordon`), and neither method should be read
as a point estimate.
"""))
    c.append(md("## 7. Sensitivity heat maps (base case)"))
    c.append(code('''
from icbp_valuation.dcf import sensitivity_wacc_g, sensitivity_wacc_exit
g1, g2 = sensitivity_wacc_g(fin, a), sensitivity_wacc_exit(fin, a)
bi = a["sensitivity"]["wacc_deltas"].index(0.0)
display(Image(plots.plot_heatmap(g1, price, "Value per share: WACC x terminal growth (Gordon TV, base case)",
        "Terminal growth g", "heatmap_wacc_g.png", (bi, a["sensitivity"]["terminal_growth"].index(0.04)))))
display(Image(plots.plot_heatmap(g2, price, "Value per share: WACC x exit EV/EBITDA (base case)",
        "Exit EV/EBITDA", "heatmap_wacc_exit_multiple.png", (bi, a["sensitivity"]["exit_multiples"].index(7.0)))))
'''))
    c.append(md("### Reverse DCF - what discount rate does the market price imply?"))
    c.append(code('''
from icbp_valuation.dcf import implied_wacc
w_g = implied_wacc(fin, a, method="gordon")
w_x = implied_wacc(fin, a, method="exit_multiple")
print(f"Base-case drivers, Gordon TV  : price IDR {price:,.0f} implies WACC = {w_g:.2%}")
print(f"Base-case drivers, exit-mult. : price IDR {price:,.0f} implies WACC = {w_x:.2%}")
print(f"Computed WACC {base['computed_wacc']:.2%}; base case uses {base['wacc']:.2%}")
'''))
    c.append(md("""
At the base operating assumptions the market price is consistent with a discount rate of roughly 14-15%
(under either terminal method), versus 9.3% in the base case. Either the market is pricing in much weaker growth or
margins than the base case, or it demands a much higher return - or this simple model is too generous.
That tension is the main result, and it is more informative than the point estimate.
"""))
    c.append(md("## 8. Walk from the Excel value to the extended model"))
    c.append(code('''
from icbp_valuation.dcf import bridge_walk
walk = bridge_walk(fin, a)
display(walk.style.format({"value_per_share": "{:,.0f}", "change": "{:+,.0f}", "vs_price": "{:+.0%}"}))
display(Image(plots.plot_bridge(walk, price)))
'''))
    c.append(md("""
Order matters (effects interact), so treat each step as indicative. Take-away: the workbook's 20,397 is the net of a
large conservative error (NWC definition, +14k) and large aggressive choices (g = 5%, low WACC).

## 9. Limitations

- Inputs are transcribed from a course workbook and not re-verified against filings; FY2023/FY2024 balance sheets do not balance.
- Equity bridge uses **book** NCI and associates; leases, pensions and minority put options are ignored.
- Valuation date is 31 Dec 2025 while the price is May 2026 (no roll-forward).
- CAPM inputs are carried from the workbook; the +2.0 pp WACC adjustment and all scenario drivers are analyst judgements.
- Single-company model; no peer-multiple or regression work; no forward-looking guidance from management.

*Educational analysis, not investment advice.*
"""))
    return nb


FX_SETUP = SETUP.replace("price = fin[\"market\"][\"share_price_idr\"]\n", "")


def fx_notebook() -> nbf.NotebookNode:
    nb = nbf.v4.new_notebook()
    c = nb.cells
    c.append(md("""
# FX transaction exposure: natural hedge vs forward vs option (illustrative)

> **Educational analysis, not investment advice.**

**Why the numbers here are invented.** The course assignment used a fictional company supplied with the module
(round-number positions, a lecturer-defined case). Since it is not a real firm's disclosure, this notebook does not
reuse it. Instead it rebuilds the *method* on a **fully fictional company with illustrative numbers** defined in the
`fx_case` block of `assumptions.yaml`. Spot levels, volatilities, correlations and interest rates are **not market data**.

Method: (1) net monetary position per currency, (2) variance-covariance VaR with and without diversification,
(3) Monte Carlo comparison of unhedged, natural, forward and option hedges at a 6-month tenor.
"""))
    c.append(code(FX_SETUP + '''
from icbp_valuation import fx_exposure as fx
case = a["fx_case"]
'''))
    c.append(md("## 1. Net monetary position"))
    c.append(code('''
net = fx.net_positions(case)
display(net[["assets_fcy", "liabilities_fcy", "net_fcy", "spot", "net_idr", "position"]]
        .style.format({"assets_fcy": "{:,.0f}", "liabilities_fcy": "{:,.0f}", "net_fcy": "{:,.0f}",
                       "spot": "{:,.0f}", "net_idr": "{:,.0f}"}))
print(f"Gross FX assets  : IDR {net['assets_idr'].sum()/1e9:,.1f} bn   Gross FX liabilities: IDR {net['liabilities_idr'].sum()/1e9:,.1f} bn")
print(f"Net position     : IDR {net['net_idr'].sum()/1e9:,.1f} bn (negative = net short foreign currency)")
'''))
    c.append(md("""
The book is net **short** CNY and JPY (import payables) and net **long** USD and EUR (export receivables). Long and short
positions in different currencies partly offset only to the extent the currencies co-move, which is what the VaR step measures.
"""))
    c.append(md("## 2. Value at risk (1 year, 99%, variance-covariance)"))
    c.append(code('''
v = fx.parametric_var(case)
tbl = pd.Series(v["standalone"], name="stand-alone VaR (IDR bn)") / 1e9
display(tbl.to_frame().style.format("{:,.2f}"))
print(f"Sum of stand-alone VaRs (no diversification): IDR {v['undiversified']/1e9:,.2f} bn")
print(f"Diversified portfolio VaR                    : IDR {v['diversified']/1e9:,.2f} bn  (z = {v['z']:.3f})")
paths = fx.simulate_paths(case)
display(Image(plots.plot_fx_paths(case, paths, net["net_fcy"])))
'''))
    c.append(md("""
Summing stand-alone VaRs overstates risk when currencies are imperfectly correlated; the diversified figure is lower.
(The course workbook summed stand-alone figures; see the audit in the DCF notebook.)
"""))
    c.append(md("## 3. Hedge comparison (Monte Carlo, 6-month tenor)"))
    c.append(code('''
t = case["horizon_days"] / case["business_days_per_year"]
fw = pd.DataFrame({
    "spot": [case["spot_idr"][k] for k in fx.CCYS],
    "forward (CIP)": [fx.forward_rate(case["spot_idr"][k], case["rates"]["IDR"], case["rates"][k], t) for k in fx.CCYS],
}, index=fx.CCYS)
fw["forward premium"] = fw["forward (CIP)"] / fw["spot"] - 1
display(fw.style.format({"spot": "{:,.0f}", "forward (CIP)": "{:,.2f}", "forward premium": "{:.2%}"}))
summary, samples = fx.hedge_comparison(case)
display(summary.style.format("{:,.1f}", subset=summary.columns[:3]).format("{:.0%}", subset=summary.columns[3:]))
display(Image(plots.plot_hedge_distribution(samples, case["confidence"])))
'''))
    c.append(md("""
**What to take from it**

- A 100% forward removes variance but locks in the **forward points**: because IDR rates are above foreign rates, buying
  CNY/JPY forward costs more than spot. That carry is the negative mean P&L, a real cost of the hedge
  even though spot is simulated with zero drift.
- Options keep the favourable tail but cost a premium up front, so mean P&L is lower than unhedged and variance falls less.
- A natural hedge (re-invoicing part of sales in CNY) reduces exposure at no instrument cost, but only as far as commercial
  terms allow. Combining it with a forward on the residual is the cheapest way to reach zero variance here.
- Not modelled: hedge accounting (PSAK 71 / IFRS 9), bank spreads, credit lines, basis risk, hedging forecast (not yet
  recognised) cash flows, and any view on the direction of rates.

*Illustrative and fictional; educational analysis, not investment advice.*
"""))
    return nb


def main() -> None:
    nbdir = ROOT / "notebooks"
    nbdir.mkdir(exist_ok=True)
    for name, nb in (("icbp_dcf.ipynb", dcf_notebook()), ("fx_exposure_illustrative.ipynb", fx_notebook())):
        nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
        path = nbdir / name
        nbf.write(nb, path)
        subprocess.run([sys.executable, "-m", "jupyter", "nbconvert", "--to", "notebook", "--execute",
                        "--inplace", "--ExecutePreprocessor.timeout=300", str(path)], check=True)
        print("executed", path)


if __name__ == "__main__":
    main()
