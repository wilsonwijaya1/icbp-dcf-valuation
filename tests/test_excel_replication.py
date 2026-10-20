import pytest

from icbp_valuation.config import historical_table
from icbp_valuation.dcf import bridge_walk, replicate_workbook, run_scenario
from icbp_valuation.verify import compare


def test_all_workbook_outputs_match_excel(fin, assumptions):
    df = compare(fin, assumptions)
    assert len(df) >= 25
    assert df["match"].all(), df[~df["match"]]


def test_headline_excel_value_per_share(fin, assumptions):
    assert replicate_workbook(fin, assumptions)["intrinsic_value_per_share"] == pytest.approx(
        20396.74454, abs=1e-4)


def test_income_statement_derivations(fin):
    h = historical_table(fin)
    assert h.loc[2025, "ebit"] == 15873652
    assert h.loc[2025, "net_income"] == 9224927


def test_documented_balance_sheet_gaps(fin):
    """Audit finding: the workbook balance sheet does not balance in FY2023/FY2024."""
    h = historical_table(fin)
    assert h.loc[2025, "balance_check_gap"] == 0
    assert h.loc[2023, "balance_check_gap"] == 100
    assert h.loc[2024, "balance_check_gap"] == 75521


def test_workbook_nwc_includes_cash_but_operating_nwc_does_not(fin):
    h = historical_table(fin)
    d_wb = h.loc[2025, "wc_total"] - h.loc[2024, "wc_total"]
    d_op = h.loc[2025, "nwc_operating"] - h.loc[2024, "nwc_operating"]
    assert d_wb == 5094940
    assert d_op < 0.4 * d_wb


def test_bridge_starts_at_excel_and_ends_at_headline(fin, assumptions):
    walk = bridge_walk(fin, assumptions)
    assert walk["value_per_share"].iloc[0] == pytest.approx(20396.74454, abs=1e-4)
    assert walk["value_per_share"].iloc[-1] == pytest.approx(
        run_scenario(fin, assumptions)["per_share"])
    assert walk["change"].iloc[1:].sum() == pytest.approx(
        walk["value_per_share"].iloc[-1] - walk["value_per_share"].iloc[0])
