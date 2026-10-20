import pytest

from icbp_valuation.wacc import (after_tax_cost_of_debt, capital_weights, compute_wacc,
                                 cost_of_equity, wacc_from_parts)


def test_capm_cost_of_equity():
    assert cost_of_equity(0.0475, 0.60, 0.075) == pytest.approx(0.0925)


def test_after_tax_cost_of_debt():
    assert after_tax_cost_of_debt(0.05, 0.22) == pytest.approx(0.039)


def test_weights_sum_to_one():
    we, wd = capital_weights(60.0, 40.0)
    assert (we, wd) == (pytest.approx(0.6), pytest.approx(0.4))


def test_wacc_hand_calculation():
    # 60% equity at 10%, 40% debt at 3% after tax -> 7.2%
    assert wacc_from_parts(0.10, 0.03, 0.6, 0.4) == pytest.approx(0.072)


def test_wacc_matches_excel_inputs():
    """Inputs of 'FCFF & DCF'!B27:B46 (tax = FY2025 tax / EBT); Excel result 7.264077594%."""
    w = compute_wacc(risk_free=0.0475, beta=0.6, erp=0.075, interest_expense=2153025,
                     total_debt=47431527, tax_rate=3080105 / 13836214,
                     share_price=7650, shares_mn=11662)
    assert w.wacc == pytest.approx(0.07264077594, abs=1e-11)
    assert w.weight_equity + w.weight_debt == pytest.approx(1.0)
