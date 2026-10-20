"""Compare the Python replica with values cached in the original Excel workbook."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .config import PROJECT_ROOT, load_assumptions, load_financials
from .dcf import replicate_workbook

SCALARS = ["cost_of_equity", "pretax_cost_of_debt", "after_tax_cost_of_debt", "market_cap",
           "total_debt", "weight_equity", "weight_debt", "wacc", "terminal_growth",
           "fcff_next", "firm_value", "net_debt", "equity_value", "shares_mn",
           "intrinsic_value_per_share", "market_price", "premium_to_price"]
SERIES = ["nopat", "delta_nwc", "fcff"]


def load_reference(path: str | Path | None = None) -> dict:
    path = Path(path) if path else PROJECT_ROOT / "data" / "excel_reference.json"
    return json.loads(Path(path).read_text(encoding="utf-8"))


def compare(fin: dict | None = None, a: dict | None = None,
            ref: dict | None = None) -> pd.DataFrame:
    """Row-by-row comparison of every key output of the workbook's DCF sheet."""
    fin = fin or load_financials()
    a = a or load_assumptions()
    ref = ref or load_reference()
    rep = replicate_workbook(fin, a)
    tol = a["verification"]["relative_tolerance"]
    rows = []
    cells = ref["cells"]
    for k in SERIES:
        for y, cell in cells[k].items():
            rows.append((f"{k} {y}", f"FCFF & DCF!{cell}", rep[k][int(y)], ref["values"][k][y]))
    for k in SCALARS:
        rows.append((k, f"FCFF & DCF!{cells[k]}", rep[k], ref["values"][k]))
    df = pd.DataFrame(rows, columns=["item", "excel_cell", "python", "excel"])
    df["abs_diff"] = (df["python"] - df["excel"]).abs()
    df["rel_diff"] = df["abs_diff"] / df["excel"].abs().where(df["excel"] != 0, 1.0)
    df["match"] = df["rel_diff"] <= tol
    return df
