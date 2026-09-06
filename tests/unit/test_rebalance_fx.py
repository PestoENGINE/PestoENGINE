"""FX integration at the Decimal rebalancing boundary."""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.fx.ecb_provider import EcbFxProvider
from app.market_data.provider_registry import ProviderRegistry
from app.schemas.request import RebalanceRequest
from app.services.rebalance_service import run_rebalance
from tests.helpers import make_quote


def _request() -> RebalanceRequest:
    return RebalanceRequest(
        only_buy=True,
        increment=Decimal("100"),
        base_currency="EUR",
        fractional_shares=True,
        assets=[
            {
                "ticker": "EUR_ASSET",
                "currency": "EUR",
                "desired_percentage": 50,
                "shares": 1,
                "fees": 0,
            },
            {
                "ticker": "USD_ASSET",
                "currency": "USD",
                "desired_percentage": 50,
                "shares": 1,
                "fees": 0,
            },
        ],
    )


def test_quotes_are_converted_before_values_percentages_and_trades():
    registry = MagicMock(spec=ProviderRegistry)
    registry.get_quotes_for_assets.return_value = list(({
        "EUR_ASSET": make_quote("100", currency="EUR"),
        "USD_ASSET": make_quote("100", currency="USD"),
    }).values())
    fx_provider = MagicMock(spec=EcbFxProvider)
    fx_provider.get_rates.return_value = {
        "USD": Decimal("0.51234567"),
    }

    result = run_rebalance(_request(), registry, fx_provider)
    by_ticker = {item.ticker: item for item in result.results}
    usd_value = Decimal("51.234567")
    total = Decimal("100") + usd_value

    assert by_ticker["EUR_ASSET"].current_percentage == pytest.approx(Decimal("10000") / total)
    assert by_ticker["USD_ASSET"].current_percentage == pytest.approx(usd_value * 100 / total)
    assert by_ticker["USD_ASSET"].ticker_price == usd_value
    fx_provider.get_rates.assert_called_once_with({"USD"}, "EUR")


@pytest.mark.parametrize("currency", ["EUR", "USD"])
def test_same_currency_portfolio_does_not_touch_fx_provider(currency):
    request = RebalanceRequest(
        only_buy=True,
        increment=100,
        base_currency=currency,
        assets=[
            {
                "ticker": "A",
                "currency": currency,
                "desired_percentage": 100,
                "shares": 0,
                "fees": 0,
            },
        ],
    )
    registry = MagicMock(spec=ProviderRegistry)
    registry.get_quotes_for_assets.return_value = list(({
        "A": make_quote("25", currency=currency),
    }).values())
    fx_provider = MagicMock(spec=EcbFxProvider)

    result = run_rebalance(request, registry, fx_provider)

    assert result.results[0].buy == 4
    fx_provider.get_rates.assert_not_called()
