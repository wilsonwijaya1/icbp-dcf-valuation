import numpy as np
import pytest

from icbp_valuation.dcf import (implied_wacc, run_all_scenarios, run_scenario,
                                sensitivity_wacc_exit, sensitivity_wacc_g)


def test_center_of_wacc_g_grid_equals_base_case(fin, assumptions):
    base = run_scenario(fin, assumptions, "base")
    grid = sensitivity_wacc_g(fin, assumptions)
    i = assumptions["sensitivity"]["wacc_deltas"].index(0.0)
    j = assumptions["sensitivity"]["terminal_growth"].index(base["terminal_growth"])
    assert grid.iloc[i, j] == pytest.approx(base["per_share_gordon"])


def test_center_of_wacc_exit_grid_equals_base_case(fin, assumptions):
    base = run_scenario(fin, assumptions, "base")
    grid = sensitivity_wacc_exit(fin, assumptions)
    i = assumptions["sensitivity"]["wacc_deltas"].index(0.0)
    j = assumptions["sensitivity"]["exit_multiples"].index(base["exit_multiple"])
    assert grid.iloc[i, j] == pytest.approx(base["per_share_exit"])


def test_value_falls_with_wacc_and_rises_with_g(fin, assumptions):
    grid = sensitivity_wacc_g(fin, assumptions).values
    assert np.all(np.diff(grid, axis=0) < 0)        # higher WACC -> lower value
    assert np.all(np.diff(grid, axis=1) > 0)        # higher g -> higher value


def test_scenario_ordering(fin, assumptions):
    r = run_all_scenarios(fin, assumptions)
    assert r["bear"]["per_share"] < r["base"]["per_share"] < r["bull"]["per_share"]


def test_reverse_dcf_reproduces_price(fin, assumptions):
    base = run_scenario(fin, assumptions, "base")
    w = implied_wacc(fin, assumptions)
    again = run_scenario(fin, assumptions, "base",
                         {"wacc_adjustment": w - base["computed_wacc"]})
    assert again["per_share_gordon"] == pytest.approx(base["market_price"], rel=1e-6)


def test_headline_is_blend_of_both_methods(fin, assumptions):
    r = run_scenario(fin, assumptions, "base")
    w = assumptions["valuation"]["blend_weight_gordon"]
    assert r["per_share"] == pytest.approx(
        w * r["per_share_gordon"] + (1 - w) * r["per_share_exit"])
