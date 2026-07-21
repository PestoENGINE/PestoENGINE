"""Configuration policy for the public ECB FX feed."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _settings(**kwargs) -> Settings:
    return Settings(
        _env_file=None, market_data_providers=["yahoo"], cache_backend="local", **kwargs,
    )


def test_ecb_fx_defaults_are_safe_for_weekends_and_holidays():
    settings = _settings()

    assert settings.fx_cache_ttl_seconds == 3600
    assert settings.ecb_fx_max_age_days == 7


def test_base_currency_normalizes_overrides():
    assert _settings(base_currency=[" chf ", " usd "]).base_currency == ["CHF", "USD"]


def test_base_currency_entries_must_be_valid():
    with pytest.raises(ValidationError, match="three-letter currency codes"):
        _settings(base_currency=["EURO"])

    with pytest.raises(ValidationError, match="must be unique"):
        _settings(base_currency=["EUR", "eur"])


def test_fx_cache_policy_rejects_invalid_values():
    with pytest.raises(ValidationError):
        _settings(fx_cache_ttl_seconds=0)
    assert _settings(ecb_fx_max_age_days=0).ecb_fx_max_age_days == 0
    with pytest.raises(ValidationError):
        _settings(ecb_fx_max_age_days=-1)
