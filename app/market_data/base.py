"""Abstract interfaces for market data providers."""

from abc import ABC, abstractmethod

from app.market_data.quote import MarketQuote


class AbstractMarketDataProvider(ABC):
    @abstractmethod
    def get_quotes(
        self,
        tickers: list[str],
        *,
        currency_hints: dict[str, str] | None = None,
    ) -> dict[str, MarketQuote]: ...


class AbstractTickerSearchProvider(ABC):
    @abstractmethod
    def search(self, q: str) -> list[dict]: ...
