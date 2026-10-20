import numpy as np
import pytest

from icbp_valuation import fx_exposure as fx


def test_net_positions(assumptions):
    n = fx.net_positions(assumptions["fx_case"])
    assert n.loc["USD", "net_fcy"] == 900000
    assert n.loc["CNY", "net_fcy"] == -18000000
    assert n.loc["CNY", "position"] == "net short (liability)"


def test_covered_interest_parity_forward():
    f = fx.forward_rate(16500.0, 0.055, 0.04, 0.5)
    assert f == pytest.approx(16500 * 1.0275 / 1.02)
    assert fx.forward_rate(100.0, 0.03, 0.03, 1.0) == pytest.approx(100.0)


def test_garman_kohlhagen_put_call_parity():
    s, k, rd, rf, v, t = 2300.0, 2350.0, 0.055, 0.015, 0.06, 0.5
    c = fx.gk_option(s, k, rd, rf, v, t, "call")
    p = fx.gk_option(s, k, rd, rf, v, t, "put")
    assert c - p == pytest.approx(s * np.exp(-rf * t) - k * np.exp(-rd * t))


def test_var_diversification_benefit(assumptions):
    v = fx.parametric_var(assumptions["fx_case"])
    assert 0 < v["diversified"] <= v["undiversified"]


def test_z_score_99():
    assert fx.z_score(0.99) == pytest.approx(2.3263, abs=1e-4)


def test_full_forward_hedge_removes_variance_and_simulation_is_reproducible(assumptions):
    s1, _ = fx.hedge_comparison(assumptions["fx_case"])
    s2, _ = fx.hedge_comparison(assumptions["fx_case"])
    assert s1.loc["Forward 100%", "std dev (IDR mn)"] == pytest.approx(0.0, abs=1e-6)
    assert s1.equals(s2)
    assert s1.loc["Unhedged", "std dev (IDR mn)"] > s1.loc["Forward 50%", "std dev (IDR mn)"]
