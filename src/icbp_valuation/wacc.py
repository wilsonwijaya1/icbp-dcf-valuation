"""Cost of capital building blocks (CAPM + after-tax cost of debt)."""
from __future__ import annotations

from dataclasses import dataclass


def cost_of_equity(risk_free: float, beta: float, erp: float) -> float:
    """CAPM: Ke = Rf + beta x ERP."""
    return risk_free + beta * erp


def after_tax_cost_of_debt(pretax_kd: float, tax_rate: float) -> float:
    """Kd x (1 - T)."""
    return pretax_kd * (1.0 - tax_rate)


def capital_weights(market_cap: float, total_debt: float) -> tuple[float, float]:
    """Market-value equity weight and book-value debt weight."""
    total = market_cap + total_debt
    we = market_cap / total
    return we, 1.0 - we


def wacc_from_parts(ke: float, kd_after_tax: float, we: float, wd: float) -> float:
    return we * ke + wd * kd_after_tax


@dataclass(frozen=True)
class WaccResult:
    risk_free: float
    beta: float
    erp: float
    cost_of_equity: float
    pretax_cost_of_debt: float
    tax_rate: float
    after_tax_cost_of_debt: float
    market_cap: float
    total_debt: float
    weight_equity: float
    weight_debt: float
    wacc: float

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def compute_wacc(*, risk_free: float, beta: float, erp: float,
                 interest_expense: float, total_debt: float, tax_rate: float,
                 share_price: float, shares_mn: float) -> WaccResult:
    """Full WACC from primitives. Money in IDR million, shares in millions."""
    ke = cost_of_equity(risk_free, beta, erp)
    kd = interest_expense / total_debt
    kd_at = after_tax_cost_of_debt(kd, tax_rate)
    mcap = share_price * shares_mn
    we, wd = capital_weights(mcap, total_debt)
    return WaccResult(risk_free, beta, erp, ke, kd, tax_rate, kd_at, mcap, total_debt,
                      we, wd, wacc_from_parts(ke, kd_at, we, wd))
