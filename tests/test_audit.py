import math

import pytest

from icbp_valuation.audit import audit_findings, fx_var_recalc


def test_audit_has_all_findings(fin, assumptions):
    df = audit_findings(fin, assumptions)
    assert len(df) == 10
    assert set(df.columns) == {"area", "finding", "workbook", "recomputed", "impact"}


def test_fx_var_recalc_scales_with_sqrt_of_days():
    out = fx_var_recalc(9_224_927)
    ratio = (out["sqrt252 (trading days)"]["total_idr_mn"]
             / out["sqrt365 (workbook)"]["total_idr_mn"])
    assert ratio == pytest.approx(math.sqrt(252 / 365))
    assert out["sqrt365 (workbook)"]["total_idr_mn"] == pytest.approx(6_769_141.866, rel=1e-6)
