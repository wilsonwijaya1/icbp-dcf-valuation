import pytest

from icbp_valuation import load_assumptions, load_financials


@pytest.fixture(scope="session")
def fin():
    return load_financials()


@pytest.fixture(scope="session")
def assumptions():
    return load_assumptions()
