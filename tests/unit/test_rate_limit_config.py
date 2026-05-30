"""Unit tests for rate-limit config fields and validator."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _settings(**kwargs) -> Settings:
    defaults = {
        "market_data_providers": ["yahoo"],
        "cache_backend": "local",
    }
    defaults.update(kwargs)
    return Settings(_env_file=None, **defaults)


def test_rate_limit_disabled_by_default():
    s = _settings()
    assert s.rate_limit_providers_per_min is None


def test_rate_limit_accepts_positive_int():
    s = _settings(rate_limit_providers_per_min=30)
    assert s.rate_limit_providers_per_min == 30


def test_rate_limit_rejects_zero():
    with pytest.raises(ValidationError, match="positive integer"):
        _settings(rate_limit_providers_per_min=0)


def test_rate_limit_rejects_negative():
    with pytest.raises(ValidationError, match="positive integer"):
        _settings(rate_limit_providers_per_min=-5)


def test_trusted_proxies_none_by_default():
    s = _settings()
    assert s.trusted_proxies is None


def test_trusted_proxies_accepts_wildcard():
    s = _settings(trusted_proxies="*")
    assert s.trusted_proxies == "*"


def test_trusted_proxies_accepts_ip_list():
    s = _settings(trusted_proxies="1.2.3.4,5.6.7.8")
    assert s.trusted_proxies == "1.2.3.4,5.6.7.8"
