import pytest

from icbp_valuation.config import historical_table
from icbp_valuation.dcf import (equity_bridge, exit_multiple_terminal_value, fcff,
                                gordon_terminal_value, implied_growth_from_exit, present_value,
                                pv_of_flows, run_scenario, terminal_fcff_next)


def test_present_value():
    assert present_value(121.0, 0.10, 2) == pytest.approx(100.0)


def test_pv_of_flows_is_sum_of_pvs():
    flows = [100.0, 110.0, 120.0]
    expected = 100 / 1.08 + 110 / 1.08**2 + 120 / 1.08**3
    assert pv_of_flows(flows, 0.08) == pytest.approx(expected)


def test_fcff_identity():
    assert fcff(nopat=100, da=20, capex=30, delta_nwc=5) == 85


def test_gordon_terminal_value():
    assert gordon_terminal_value(104.0, 0.10, 0.04) == pytest.approx(104 / 0.06)


def test_gordon_rejects_wacc_not_above_g():
    with pytest.raises(ValueError):
        gordon_terminal_value(100, 0.05, 0.05)


def test_exit_multiple_terminal_value():
    assert exit_multiple_terminal_value(200.0, 7.5) == 1500.0


def test_terminal_fcff_is_consistent_with_growth():
    # zero growth -> terminal FCFF equals NOPAT + D&A - capex (no NWC build)
    assert terminal_fcff_next(100, 20, 30, 0.1, 1000, 0.0) == pytest.approx(90)
    # growth adds NWC investment of nwc_pct * revenue * g
    assert terminal_fcff_next(100, 20, 30, 0.1, 1000, 0.04) == pytest.approx(
        90 * 1.04 - 0.1 * 1000 * 0.04)


def test_implied_growth_round_trip():
    nopat, da, capex, pct, rev, w = 100.0, 20.0, 30.0, 0.1, 1000.0, 0.09
    tv = gordon_terminal_value(terminal_fcff_next(nopat, da, capex, pct, rev, 0.03), w, 0.03)
    assert implied_growth_from_exit(tv, w, nopat, da, capex, pct, rev) == pytest.approx(0.03)


def test_equity_bridge_modes(fin):
    h25 = historical_table(fin).loc[2025]
    simple = equity_bridge(1_000_000.0, h25, "net_debt_only")
    full = equity_bridge(1_000_000.0, h25, "full")
    assert simple["equity_value"] == pytest.approx(1_000_000 - h25["net_debt"])
    assert full["equity_value"] == pytest.approx(
        simple["equity_value"] - h25["non_controlling_equity"] + h25["long_term_investments"])


def test_ev_is_pv_fcff_plus_pv_tv(fin, assumptions):
    r = run_scenario(fin, assumptions, "base")
    assert r["ev_gordon"] == pytest.approx(r["pv_fcff"] + r["pv_tv_gordon"])
    assert r["ev_exit"] == pytest.approx(r["pv_fcff"] + r["pv_tv_exit"])
    n = len(r["projection"])
    assert r["pv_tv_gordon"] == pytest.approx(r["tv_gordon"] / (1 + r["wacc"]) ** n)
