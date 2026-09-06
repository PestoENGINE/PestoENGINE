"""Pydantic v2 schemas for the HTTP request boundary."""

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from app.core.config import ProviderId, get_validation_settings
from app.market_data.quote import normalize_currency


class AssetIn(BaseModel):
    ticker: str = Field(min_length=1, max_length=64)
    provider: ProviderId | None = None
    currency: str | None = None
    desired_percentage: Decimal = Field(ge=0, le=100, max_digits=9, decimal_places=6)
    shares: Decimal = Field(ge=0, le=Decimal("1e12"), max_digits=19, decimal_places=6)
    fees: Decimal = Field(ge=0, le=Decimal("1e12"), max_digits=19, decimal_places=6)
    percentage_fee: bool = False

    @field_validator("ticker", mode="before")
    @classmethod
    def normalize_ticker(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip().upper()
            if any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value):
                raise ValueError("ticker cannot contain whitespace or control characters")
        return value

    @field_validator("provider", mode="before")
    @classmethod
    def normalize_provider(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_asset_currency(cls, value: object) -> object:
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            raise ValueError("currency must be a string")
        return normalize_currency(value)

    @model_validator(mode="after")
    def check_percentage_fee_cap(self) -> "AssetIn":
        if self.percentage_fee and self.fees > 100:
            # Stable code + ctx so the client can localize without parsing prose.
            raise PydanticCustomError(
                "percentage_fee_cap",
                "Asset '{ticker}': percentage fee cannot exceed 100, got {fees}",
                {"ticker": self.ticker, "fees": self.fees},
            )
        return self


class RebalanceRequest(BaseModel):
    only_buy: bool
    increment: Decimal = Field(ge=0, le=Decimal("1e12"), max_digits=19, decimal_places=6)
    base_currency: str
    optimal_redistribute: bool = False
    fractional_shares: bool = False
    assets: list[AssetIn] = Field(min_length=1, max_length=100)

    @field_validator("base_currency", mode="before")
    @classmethod
    def normalize_base_currency(cls, value: object) -> object:
        allowed = get_validation_settings().base_currency
        if not isinstance(value, str):
            return value
        try:
            normalized = normalize_currency(value)
        except ValueError:
            normalized = ""
        if normalized not in allowed:
            raise ValueError("base_currency must be one of: " + ", ".join(allowed))
        return normalized

    @model_validator(mode="after")
    def check_percentages_sum(self) -> "RebalanceRequest":
        total = sum(a.desired_percentage for a in self.assets)
        if total != 100:
            # Stable code + ctx so the client can localize without parsing prose.
            raise PydanticCustomError(
                "percentage_sum",
                "desired_percentage must sum to 100.00, got {total}",
                {"total": float(total)},
            )
        return self
