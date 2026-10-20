"""`python -m icbp_valuation` : run verification, scenarios, sensitivities, FX study and
regenerate the figures and CSV tables under reports/."""
from __future__ import annotations

import pandas as pd

from . import fx_exposure as fx
from . import plots
from .config import PROJECT_ROOT, historical_table, load_assumptions, load_financials
from .dcf import (bridge_walk, implied_wacc, market_implied_ev_ebitda, run_all_scenarios,
                  scenario_table, sensitivity_wacc_exit, sensitivity_wacc_g)
from .audit import audit_findings
from .verify import compare


def main() -> None:
    pd.set_option("display.width", 200)
    pd.set_option("display.float_format", "{:,.4f}".format)
    fin, a = load_financials(), load_assumptions()
    tables = PROJECT_ROOT / "reports" / "tables"
    tables.mkdir(parents=True, exist_ok=True)

    cmp = compare(fin, a)
    print("== Python replica vs Excel: %d/%d items match (rel tol %.0e)" %
          (cmp["match"].sum(), len(cmp), a["verification"]["relative_tolerance"]))
    cmp.to_csv(tables / "excel_vs_python.csv", index=False)

    audit_findings(fin, a).to_csv(tables / "excel_audit_findings.csv", index=False)

    res = run_all_scenarios(fin, a)
    st = scenario_table(res)
    print(st.T)
    st.to_csv(tables / "scenarios.csv")
    price = fin["market"]["share_price_idr"]

    walk = bridge_walk(fin, a)
    print(walk)
    walk.to_csv(tables / "bridge_walk.csv", index=False)

    g1, g2 = sensitivity_wacc_g(fin, a), sensitivity_wacc_exit(fin, a)
    g1.to_csv(tables / "sensitivity_wacc_g.csv")
    g2.to_csv(tables / "sensitivity_wacc_exit.csv")
    base_i = a["sensitivity"]["wacc_deltas"].index(0.0)
    plots.plot_heatmap(g1, price, "Value per share: WACC x terminal growth (Gordon TV, base case)",
                       "Terminal growth g", "heatmap_wacc_g.png",
                       (base_i, a["sensitivity"]["terminal_growth"].index(
                           a["extended"]["scenarios"]["base"]["terminal_growth"])))
    plots.plot_heatmap(g2, price, "Value per share: WACC x exit EV/EBITDA (base case)",
                       "Exit EV/EBITDA", "heatmap_wacc_exit_multiple.png",
                       (base_i, a["sensitivity"]["exit_multiples"].index(
                           a["extended"]["scenarios"]["base"]["exit_ev_ebitda"])))
    plots.plot_scenarios(res, price)
    plots.plot_bridge(walk, price)
    plots.plot_fcff(fin, a, res["base"])
    print("market-implied EV/EBITDA: %.2fx" % market_implied_ev_ebitda(fin))
    print("reverse-DCF WACC (Gordon, base drivers): %.2f%%" % (100 * implied_wacc(fin, a)))

    case = a["fx_case"]
    net = fx.net_positions(case)
    paths = fx.simulate_paths(case)
    plots.plot_fx_paths(case, paths, net["net_fcy"])
    summary, samples = fx.hedge_comparison(case)
    plots.plot_hedge_distribution(samples, case["confidence"])
    summary.to_csv(tables / "fx_hedge_comparison.csv")
    print(summary)
    print("figures ->", plots.FIG_DIR)


if __name__ == "__main__":
    main()
