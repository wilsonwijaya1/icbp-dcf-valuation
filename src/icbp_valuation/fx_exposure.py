"""Illustrative transaction-exposure study: net positions, VaR, and a comparison of
natural hedge vs forward vs option hedging by Monte Carlo.

IMPORTANT: every input comes from the `fx_case` block of assumptions.yaml and is
fictional / illustrative. Nothing here is real market data or a real company.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

CCYS = ["USD", "EUR", "CNY", "JPY"]


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def z_score(conf: float) -> float:
    """Standard normal quantile by bisection on the CDF."""
    lo, hi = -10.0, 10.0
    while hi - lo > 1e-12:
        mid = (lo + hi) / 2
        if norm_cdf(mid) < conf:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def net_positions(case: dict) -> pd.DataFrame:
    """Assets, liabilities and net position per currency (FCY and IDR at spot)."""
    rows = []
    for c in CCYS:
        a = sum(p["amount"] for p in case["positions"]["assets"] if p["ccy"] == c)
        liab = sum(p["amount"] for p in case["positions"]["liabilities"] if p["ccy"] == c)
        s = case["spot_idr"][c]
        rows.append({"ccy": c, "assets_fcy": a, "liabilities_fcy": liab, "net_fcy": a - liab,
                     "spot": s, "assets_idr": a * s, "liabilities_idr": liab * s,
                     "net_idr": (a - liab) * s})
    df = pd.DataFrame(rows).set_index("ccy")
    df["position"] = np.where(df["net_fcy"] > 0, "net long (asset)", "net short (liability)")
    return df


def covariance_matrix(case: dict) -> np.ndarray:
    vols = np.array([case["annual_vol"][c] for c in CCYS])
    corr = np.array(case["correlation"], dtype=float)
    return np.outer(vols, vols) * corr


def parametric_var(case: dict, net_idr: np.ndarray | None = None, horizon_years: float = 1.0,
                   conf: float | None = None) -> dict:
    """Variance-covariance VaR of the net IDR value of FX positions.
    Returns per-currency stand-alone VaR, the undiversified sum, and diversified VaR."""
    conf = conf or case["confidence"]
    if net_idr is None:
        net_idr = net_positions(case).loc[CCYS, "net_idr"].values
    cov = covariance_matrix(case)
    z = z_score(conf)
    sd = np.sqrt(horizon_years) * np.sqrt(np.einsum("i,ij,j", net_idr, cov, net_idr))
    standalone = np.abs(net_idr) * np.sqrt(horizon_years) * np.sqrt(np.diag(cov)) * z
    return {"standalone": dict(zip(CCYS, standalone)), "undiversified": float(standalone.sum()),
            "diversified": float(z * sd), "z": z}


def simulate_paths(case: dict, n_days: int | None = None, seed: int | None = None) -> pd.DataFrame:
    """Correlated geometric Brownian motion (zero drift) for IDR per FCY, daily steps."""
    n_days = n_days or case["horizon_days"]
    rng = np.random.default_rng(case["seed"] if seed is None else seed)
    dt = 1.0 / case["business_days_per_year"]
    vols = np.array([case["annual_vol"][c] for c in CCYS])
    chol = np.linalg.cholesky(np.array(case["correlation"], dtype=float))
    eps = rng.standard_normal((n_days, len(CCYS))) @ chol.T
    log_ret = -0.5 * vols**2 * dt + vols * math.sqrt(dt) * eps
    spot0 = np.array([case["spot_idr"][c] for c in CCYS])
    paths = spot0 * np.exp(np.vstack([np.zeros(len(CCYS)), np.cumsum(log_ret, axis=0)]))
    return pd.DataFrame(paths, columns=CCYS)


def forward_rate(spot: float, r_dom: float, r_for: float, t: float) -> float:
    """Covered interest parity (simple interest): F = S (1 + r_d t) / (1 + r_f t)."""
    return spot * (1.0 + r_dom * t) / (1.0 + r_for * t)


def gk_option(spot: float, strike: float, r_dom: float, r_for: float, vol: float, t: float,
              kind: str = "call") -> float:
    """Garman-Kohlhagen FX option value (IDR per 1 unit of FCY)."""
    d1 = (math.log(spot / strike) + (r_dom - r_for + 0.5 * vol**2) * t) / (vol * math.sqrt(t))
    d2 = d1 - vol * math.sqrt(t)
    df_f, df_d = math.exp(-r_for * t), math.exp(-r_dom * t)
    if kind == "call":
        return spot * df_f * norm_cdf(d1) - strike * df_d * norm_cdf(d2)
    return strike * df_d * norm_cdf(-d2) - spot * df_f * norm_cdf(-d1)


def hedge_comparison(case: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Monte Carlo (terminal spot at the hedge tenor, correlated zero-drift lognormal) P&L of
    the FX book under alternative hedging strategies. P&L is measured against the IDR value
    of the net position at today's spot, in IDR million.
    Returns (summary table, P&L samples)."""
    h = case["hedging"]
    t = case["horizon_days"] / case["business_days_per_year"]
    net = net_positions(case)
    spot0 = net.loc[CCYS, "spot"].values
    net_fcy = net.loc[CCYS, "net_fcy"].values.astype(float)
    vols = np.array([case["annual_vol"][c] for c in CCYS])
    r = case["rates"]
    fwd = np.array([forward_rate(case["spot_idr"][c], r["IDR"], r[c], t) for c in CCYS])
    rng = np.random.default_rng(case["seed"])
    chol = np.linalg.cholesky(np.array(case["correlation"], dtype=float))
    eps = rng.standard_normal((h["mc_paths"], len(CCYS))) @ chol.T
    st = spot0 * np.exp(-0.5 * vols**2 * t + vols * math.sqrt(t) * eps)

    def pnl_unhedged(n):
        return (st - spot0) * n

    def pnl_forward(n, ratio):
        return (st - spot0) * n * (1 - ratio) + (fwd - spot0) * n * ratio

    def pnl_option(n):
        out = np.zeros_like(st)
        for i, c in enumerate(CCYS):
            if n[i] == 0:
                continue
            kind = "put" if n[i] > 0 else "call"   # protect a long with a put, a short with a call
            prem = gk_option(case["spot_idr"][c], fwd[i], r["IDR"], r[c], vols[i], t, kind)
            payoff = (np.maximum(fwd[i] - st[:, i], 0) if kind == "put"
                      else np.maximum(st[:, i] - fwd[i], 0)) * abs(n[i])
            out[:, i] = ((st[:, i] - spot0[i]) * n[i] + payoff
                         - prem * abs(n[i]) * (1 + r["IDR"] * t))
        return out

    net_nat = net_fcy.copy()
    net_nat[CCYS.index("CNY")] += h["natural_hedge_cny_reinvoiced"]   # CNY sales offset CNY payables
    ratio_p = h["forward_hedge_ratio_partial"]
    strategies = {
        "Unhedged": pnl_unhedged(net_fcy).sum(axis=1),
        "Natural hedge (re-invoice CNY sales)": pnl_unhedged(net_nat).sum(axis=1),
        f"Forward {ratio_p:.0%}": pnl_forward(net_fcy, ratio_p).sum(axis=1),
        "Forward 100%": pnl_forward(net_fcy, 1.0).sum(axis=1),
        "Options 100% (ATM-forward strike)": pnl_option(net_fcy).sum(axis=1),
        "Natural + forward on residual": pnl_forward(net_nat, 1.0).sum(axis=1),
    }
    samples = pd.DataFrame(strategies) / 1e6
    q = 1 - case["confidence"]
    summary = pd.DataFrame({
        "mean P&L (IDR mn)": samples.mean(),
        "std dev (IDR mn)": samples.std(),
        f"{case['confidence']:.0%} worst-case P&L (IDR mn)": samples.quantile(q),
    })
    base_sd = summary.loc["Unhedged", "std dev (IDR mn)"]
    summary["risk reduction vs unhedged"] = 1 - summary["std dev (IDR mn)"] / base_sd
    return summary, samples
