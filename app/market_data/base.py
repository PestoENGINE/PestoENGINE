"""Abstract interfaces for market data providers."""

from abc import ABC, abstractmethod
from typing import Protocol, TypedDict

from app.market_data.quote import MarketQuote


class AssetReference(Protocol):
    @property
    def ticker(self) -> str: ...

    @property
    def provider(self) -> str | None: ...

    @property
    def currency(self) -> str | None: ...


class SearchResult(TypedDict):
    symbol: str
    name: str
    exchange: str
    type: str
    provider: str
    currency: str | None


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
    def search(self, q: str) -> list[SearchResult]: ...
