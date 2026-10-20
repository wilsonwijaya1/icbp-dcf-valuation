"""ICBP DCF valuation and illustrative FX exposure analysis (educational)."""

from .config import load_assumptions, load_financials, PROJECT_ROOT  # noqa: F401
from .dcf import (  # noqa: F401
    replicate_workbook,
    run_scenario,
    run_all_scenarios,
    bridge_walk,
)
from .wacc import compute_wacc  # noqa: F401

__version__ = "0.1.0"
