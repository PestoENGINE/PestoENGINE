"""FX conversion using the ECB Data Portal's public EXR dataset."""

import csv
import io
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

import httpx

from app.core.exceptions import MarketDataError
from app.market_data.cache import AbstractCache
from app.market_data.quote import normalize_currency

logger = logging.getLogger(__name__)

_BASE_URL = "https://data-api.ecb.europa.eu/service/data/EXR"
_CACHE_PREFIX = "fx:ecb:reference:v1"
_RETRIES = 3
_RETRY_DELAY = 1.0
_TIMEOUT_SECONDS = 10.0
_EUR = "EUR"


@dataclass(frozen=True, slots=True)
class EcbReferenceRate:
    """Foreign-currency units per euro in one ECB observation."""

    currency: str
    units_per_eur: Decimal
    as_of: date

    def __post_init__(self) -> None:
        currency = normalize_currency(self.currency)
        if currency == _EUR:
            raise ValueError("EUR is implicit in ECB reference rates")
        if not isinstance(self.units_per_eur, Decimal):
            raise TypeError("ECB reference rate must be a Decimal")
        if not self.units_per_eur.is_finite() or self.units_per_eur <= 0:
            raise ValueError("ECB reference rate must be finite and positive")
        if not isinstance(self.as_of, date):
            raise TypeError("ECB observation date must be a date")
        object.__setattr__(self, "currency", currency)

    def to_cache_dict(self) -> dict[str, str]:
        return {
            "currency": self.currency,
            "units_per_eur": str(self.units_per_eur),
            "as_of": self.as_of.isoformat(),
        }

    @classmethod
    def from_cache_dict(cls, value: object) -> "EcbReferenceRate":
        try:
            return cls(  # type: ignore[index]
                currency=value["currency"],
                units_per_eur=Decimal(value["units_per_eur"]),
                as_of=date.fromisoformat(value["as_of"]),
            )
        except (InvalidOperation, KeyError, TypeError, ValueError) as exc:
            raise ValueError("Malformed ECB cache payload") from exc


def _major_unit(currency: str) -> tuple[str, Decimal]:
    normalized = normalize_currency(currency)
    if normalized == "GBX":
        return "GBP", Decimal("0.01")
    return normalized, Decimal("1")


class EcbFxProvider:
    """Build source-to-target rates from daily ECB EUR reference rates."""

    def __init__(
        self,
        cache: AbstractCache[EcbReferenceRate],
        *,
        max_age_days: int = 7,
        today: Callable[[], date] | None = None,
    ) -> None:
        if max_age_days < 0:
            raise ValueError("max_age_days cannot be negative")
        self._cache = cache
        self._max_age_days = max_age_days
        self._today = today or (lambda: datetime.now(UTC).date())
        self._fetch_lock = threading.Lock()

    def get_rates(
        self,
        source_currencies: set[str],
        target_currency: str,
    ) -> dict[str, Decimal]:
        target = normalize_currency(target_currency)
        sources = {normalize_currency(source) for source in source_currencies} - {target}
        if not sources:
            return {}

        source_units = {source: _major_unit(source) for source in sources}
        required = {
            major
            for major, _factor in source_units.values()
            if major not in {_EUR, target}
        }
        if target != _EUR and any(major != target for major, _ in source_units.values()):
            required.add(target)
        references = self._get_reference_rates(required)
        missing = sorted(required.difference(references))
        if missing:
            raise MarketDataError(
                "ECB has no reference rate for "
                + ", ".join(missing)
                + f"; cannot convert to {target}."
            )

        rates: dict[str, Decimal] = {}
        for source in sorted(sources):
            source_major, source_factor = source_units[source]
            if source_major != target:
                source_per_eur = (
                    Decimal("1")
                    if source_major == _EUR
                    else references[source_major].units_per_eur
                )
                target_per_eur = (
                    Decimal("1")
                    if target == _EUR
                    else references[target].units_per_eur
                )
                major_rate = target_per_eur / source_per_eur
            else:
                major_rate = Decimal("1")
            rates[source] = source_factor * major_rate
        return rates

    def _get_reference_rates(
        self,
        currencies: set[str],
    ) -> dict[str, EcbReferenceRate]:
        if not currencies:
            return {}

        # Avoid duplicate ECB fetches inside one worker.
        with self._fetch_lock:
            references: dict[str, EcbReferenceRate] = {}
            missing: set[str] = set()
            for currency in currencies:
                cached = self._cache.get(f"{_CACHE_PREFIX}:{currency}")
                if cached is not None and self._is_fresh(cached):
                    references[currency] = cached
                else:
                    missing.add(currency)

            if missing:
                fetched = self._fetch_reference_rates(missing)
                for currency, reference in fetched.items():
                    self._assert_fresh(reference)
                    self._cache.set(f"{_CACHE_PREFIX}:{currency}", reference)
                    references[currency] = reference
            return references

    def _is_fresh(self, reference: EcbReferenceRate) -> bool:
        age_days = (self._today() - reference.as_of).days
        return 0 <= age_days <= self._max_age_days

    def _assert_fresh(self, reference: EcbReferenceRate) -> None:
        age_days = (self._today() - reference.as_of).days
        if age_days < 0:
            raise MarketDataError(
                f"ECB reference rate for {reference.currency} has a future "
                f"observation date ({reference.as_of.isoformat()})."
            )
        if age_days > self._max_age_days:
            raise MarketDataError(
                f"ECB reference rate for {reference.currency} is stale "
                f"({reference.as_of.isoformat()}, maximum age "
                f"{self._max_age_days} days)."
            )

    def _fetch_reference_rates(
        self,
        currencies: set[str],
    ) -> dict[str, EcbReferenceRate]:
        series = f"D.{'+'.join(sorted(currencies))}.EUR.SP00.A"
        last_error = "unknown error"
        for attempt in range(1, _RETRIES + 1):
            try:
                response = httpx.get(
                    f"{_BASE_URL}/{series}",
                    params={
                        "lastNObservations": 1,
                        "detail": "dataonly",
                        "format": "csvdata",
                    },
                    headers={"Accept": "text/csv"},
                    timeout=_TIMEOUT_SECONDS,
                )
                if response.status_code == 404:
                    return {}
                response.raise_for_status()
                return self._parse_csv(response.text, currencies)
            except (csv.Error, httpx.HTTPError, InvalidOperation, KeyError,
                    TypeError, ValueError) as exc:
                if isinstance(exc, httpx.HTTPStatusError):
                    last_error = f"HTTP {exc.response.status_code}"
                else:
                    last_error = type(exc).__name__
                logger.warning("ECB FX fetch attempt %d/%d failed: %s",
                               attempt, _RETRIES, last_error)
                if attempt < _RETRIES:
                    time.sleep(_RETRY_DELAY)
        raise MarketDataError(
            f"Could not fetch ECB rates after {_RETRIES} attempts: {last_error}."
        )

    @staticmethod
    def _parse_csv(
        body: str,
        requested: set[str],
    ) -> dict[str, EcbReferenceRate]:
        reader = csv.DictReader(io.StringIO(body))
        required = {"CURRENCY", "CURRENCY_DENOM", "TIME_PERIOD", "OBS_VALUE"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Malformed ECB CSV header")
        parsed: dict[str, EcbReferenceRate] = {}
        for row in reader:
            currency = normalize_currency(row["CURRENCY"])
            if currency not in requested:
                continue
            if row["CURRENCY_DENOM"] != _EUR:
                raise ValueError("Unexpected ECB rate denominator")
            candidate = EcbReferenceRate(
                currency=currency,
                units_per_eur=Decimal(row["OBS_VALUE"]),
                as_of=date.fromisoformat(row["TIME_PERIOD"]),
            )
            current = parsed.get(currency)
            if current is None or candidate.as_of > current.as_of:
                parsed[currency] = candidate
        return parsed
