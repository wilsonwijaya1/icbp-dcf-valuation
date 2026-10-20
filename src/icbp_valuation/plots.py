"""Matplotlib figures for the README and notebooks (saved to reports/figures)."""
from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .config import PROJECT_ROOT, historical_table  # noqa: E402
from .dcf import replicate_workbook  # noqa: E402

FIG_DIR = PROJECT_ROOT / "reports" / "figures"
C_BLUE, C_ORANGE, C_GREY, C_RED, C_GREEN = "#2a6f97", "#e07a1f", "#8a8f98", "#c0392b", "#2e8b57"
plt.rcParams.update({"figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False,
                     "font.size": 10, "axes.titleweight": "bold"})


def _save(fig, name: str, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else FIG_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_heatmap(grid: pd.DataFrame, price: float, title: str, xlabel: str, name: str,
                 base_cell: tuple[int, int] | None = None, out_dir=None) -> Path:
    """Heat map of value per share. Cells below the market price are marked with a hatch-free
    outline so the 'priced-in' frontier is visible; base cell is boxed."""
    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    vals = grid.values.astype(float)
    # diverging around the market price: <price red-ish, >price blue-ish
    norm = matplotlib.colors.TwoSlopeNorm(vmin=min(np.nanmin(vals), price * 0.8), vcenter=price,
                                          vmax=max(np.nanmax(vals), price * 1.2))
    im = ax.imshow(vals, cmap="RdBu", norm=norm, aspect="auto")
    ax.set_xticks(range(grid.shape[1]))
    ax.set_xticklabels([f"{c:.1%}" if c < 1 else f"{c:.1f}x" for c in grid.columns])
    ax.set_yticks(range(grid.shape[0]))
    ax.set_yticklabels([f"{r:.2%}" for r in grid.index])
    ax.set_xlabel(xlabel)
    ax.set_ylabel("WACC")
    ax.set_title(title)
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            v = vals[i, j]
            ax.text(j, i, "n/a" if np.isnan(v) else f"{v:,.0f}", ha="center", va="center",
                    fontsize=8, color="black")
    if base_cell:
        ax.add_patch(plt.Rectangle((base_cell[1] - .5, base_cell[0] - .5), 1, 1, fill=False,
                                   ec="black", lw=2.2))
    cb = fig.colorbar(im, ax=ax, shrink=.85)
    cb.set_label(f"IDR per share  (white = market price {price:,.0f})")
    return _save(fig, name, out_dir)


def plot_scenarios(results: dict, price: float, name="scenarios_value_per_share.png", out_dir=None):
    """Grouped bars: Gordon vs exit-multiple vs headline blend for bear/base/bull."""
    order = [s for s in ("bear", "base", "bull") if s in results]
    x = np.arange(len(order))
    w = 0.26
    fig, ax = plt.subplots(figsize=(8, 4.8))
    for k, (key, lab, col) in enumerate([("per_share_gordon", "Gordon growth TV", C_BLUE),
                                         ("per_share_exit", "Exit-multiple TV", C_ORANGE),
                                         ("per_share", "Headline (blend)", C_GREY)]):
        vals = [results[s][key] for s in order]
        bars = ax.bar(x + (k - 1) * w, vals, w, label=lab, color=col)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v, f"{v:,.0f}", ha="center", va="bottom", fontsize=8)
    ax.axhline(price, color=C_RED, ls="--", lw=1.4)

    ax.set_xticks(x)
    ax.set_xticklabels([s.capitalize() for s in order])
    ax.set_ylabel("Intrinsic value, IDR per share")
    ax.set_title("ICBP: intrinsic value by scenario vs market price")
    ax.legend(frameon=False)
    return _save(fig, name, out_dir)


def plot_bridge(walk: pd.DataFrame, price: float, name="excel_to_python_bridge.png", out_dir=None):
    """Waterfall from the Excel-as-built value to the extended headline value."""
    fig, ax = plt.subplots(figsize=(11.5, 5.4))
    labels = [s.split(". ", 1)[1] if ". " in s else s for s in walk["step"]]
    start = walk["value_per_share"].iloc[0]
    ax.bar(0, start, color=C_GREY)
    ax.text(0, start, f"{start:,.0f}", ha="center", va="bottom", fontsize=8)
    run = start
    for i in range(1, len(walk)):
        ch = walk["change"].iloc[i]
        ax.bar(i, abs(ch), bottom=min(run, run + ch), color=C_GREEN if ch >= 0 else C_RED)
        ax.text(i, max(run, run + ch), f"{ch:+,.0f}", ha="center", va="bottom", fontsize=8)
        run += ch
    ax.bar(len(walk), run, color=C_BLUE)
    ax.text(len(walk), run, f"{run:,.0f}", ha="center", va="bottom", fontsize=8)
    ax.axhline(price, color=C_RED, ls="--", lw=1.2, label=f"Market price {price:,.0f}")
    ax.legend(frameon=False, loc="upper right")
    ax.set_xticks(range(len(walk) + 1))
    wrapped = ["\n".join(__import__("textwrap").wrap(t, 16)) for t in ["Excel as built"] + labels[1:] + ["Python headline"]]
    ax.set_xticklabels(wrapped, fontsize=7)
    ax.set_ylabel("IDR per share")
    ax.set_title("Reconciling the Excel result to the extended Python model")
    return _save(fig, name, out_dir)


def plot_fcff(fin: dict, a: dict, base: dict, name="fcff_history_projection.png", out_dir=None):
    """Historical FCFF (workbook definition vs operating-NWC definition) and projected FCFF."""
    h = historical_table(fin)
    rep = replicate_workbook(fin, a)
    t = a["wacc"]["statutory_tax_rate"]
    yrs_h = [2024, 2025]
    f_wb = [rep["fcff"][y] / 1e3 for y in yrs_h]
    f_op = []
    for y in yrs_h:
        nopat = h.loc[y, "ebit"] * (1 - h.loc[y, "effective_tax_rate"])
        d = h.loc[y, "nwc_operating"] - h.loc[y - 1, "nwc_operating"]
        f_op.append((nopat + h.loc[y, "depreciation_amortization"] - h.loc[y, "capex"] - d) / 1e3)
    proj = base["projection"]
    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    x = np.arange(len(yrs_h))
    ax.bar(x - .18, f_wb, .36, color=C_GREY, label="Historical, workbook NWC (incl. cash/debt)")
    ax.bar(x + .18, f_op, .36, color=C_BLUE, label="Historical, operating NWC")
    xp = np.arange(len(yrs_h), len(yrs_h) + len(proj))
    ax.bar(xp, proj["fcff"] / 1e3, .5, color=C_ORANGE, label="Projected (base)")
    ax.set_xticks(list(x) + list(xp))
    ax.set_xticklabels([f"FY{y}" for y in yrs_h] + [f"FY{y}E" for y in proj.index])
    ax.set_ylabel("FCFF, IDR billion")
    ax.set_title("ICBP free cash flow to the firm")
    ax.legend(frameon=False, fontsize=8)
    return _save(fig, name, out_dir)


def plot_fx_paths(case: dict, paths: pd.DataFrame, net_fcy: pd.Series,
                  name="fx_net_position_path.png", out_dir=None):
    """Indexed spot paths (left) and mark-to-market value change of the net book (right)."""
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2))
    idx = paths / paths.iloc[0] * 100
    for c in paths.columns:
        axes[0].plot(idx[c], label=c)
    axes[0].set_title("Simulated IDR crosses (indexed, illustrative)")
    axes[0].set_xlabel("Business day")
    axes[0].legend(frameon=False, ncol=2)
    mtm = ((paths - paths.iloc[0]) * net_fcy.reindex(paths.columns)).sum(axis=1) / 1e6
    axes[1].plot(mtm, color=C_RED)
    axes[1].axhline(0, color="black", lw=.7)
    axes[1].set_title("Net FX book: change in IDR value")
    axes[1].set_xlabel("Business day")
    axes[1].set_ylabel("IDR million")
    return _save(fig, name, out_dir)


def plot_hedge_distribution(samples: pd.DataFrame, conf: float, name="fx_hedge_pnl_distribution.png",
                            out_dir=None):
    """Box plot of terminal P&L by hedging strategy with the VaR-style worst case marked."""
    fig, ax = plt.subplots(figsize=(9, 4.8))
    cols = list(samples.columns)
    data = [samples[c].values for c in cols]
    ax.boxplot(data, vert=False, whis=(1, 99), showfliers=False, patch_artist=True,
               boxprops=dict(facecolor="#cfe2f0"), medianprops=dict(color=C_RED))
    ax.set_yticks(range(1, len(cols) + 1))
    ax.set_yticklabels(cols, fontsize=8)
    ax.invert_yaxis()
    ax.axvline(0, color="black", lw=.7)
    ax.set_xlabel("P&L vs today's spot value, IDR million (whiskers: 1st-99th percentile)")
    ax.set_title("Illustrative hedging comparison (fictional company)")
    return _save(fig, name, out_dir)
