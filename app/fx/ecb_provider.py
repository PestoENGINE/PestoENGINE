"""FX conversion using the ECB Data Portal's public EXR dataset."""

import csv
import io
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

import httpx

from app.core.exceptions import MarketDataError, ProviderDeadlineError
from app.core.http import provider_get, remaining_budget, retry_pause, retryable, safe_error
from app.market_data.cache import AbstractCache
from app.market_data.quote import normalize_currency

logger = logging.getLogger(__name__)

_BASE_URL = "https://data-api.ecb.europa.eu/service/data/EXR"
_CACHE_PREFIX = "fx:ecb:reference:v1"
_RETRIES = 3
_RETRY_DELAY = 1.0
_TIMEOUT_SECONDS = 10.0
_EUR = "EUR"
_ONE = Decimal(1)


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
        if not self.units_per_eur.is_finite() or not Decimal(
            "1e-12"
        ) <= self.units_per_eur <= Decimal("1e12"):
            raise ValueError("ECB reference rate must be finite and positive")
        if type(self.as_of) is not date:
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
            if not isinstance(value, dict):
                raise ValueError("Expected an object")
            return cls(
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
    return normalized, _ONE


class FxRates(dict[str, Decimal]):
    """Conversion rates sharing one ECB reference date (None for unit-only FX)."""

    def __init__(self, *, as_of: date | None = None) -> None:
        super().__init__()
        self.as_of = as_of


class EcbFxProvider:
    """Build source-to-target rates from daily ECB EUR reference rates."""

    def __init__(
        self,
        cache: AbstractCache[EcbReferenceRate],
        *,
        max_age_days: int = 7,
        today: Callable[[], date] | None = None,
        client: httpx.Client | None = None,
        timeout: float = 10,
    ) -> None:
        if max_age_days < 0:
            raise ValueError("max_age_days cannot be negative")
        self._cache = cache
        self._client = client
        self._timeout = timeout
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
            major for major, _factor in source_units.values() if major not in {_EUR, target}
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

        rates = FxRates(as_of=next(iter(references.values())).as_of if references else None)
        for source in sorted(sources):
            source_major, source_factor = source_units[source]
            if source_major != target:
                source_per_eur = (
                    _ONE if source_major == _EUR else references[source_major].units_per_eur
                )
                target_per_eur = _ONE if target == _EUR else references[target].units_per_eur
                major_rate = target_per_eur / source_per_eur
            else:
                major_rate = _ONE
            rates[source] = source_factor * major_rate
        return rates

    def _get_reference_rates(
        self,
        currencies: set[str],
    ) -> dict[str, EcbReferenceRate]:
        if not currencies:
            return {}

        # A batch must use one reference date. A partial hit or mixed dates
        # refreshes the whole required set, not only the missing currencies.
        remaining = remaining_budget()
        if not self._fetch_lock.acquire(timeout=remaining if remaining is not None else -1):
            raise ProviderDeadlineError("ECB request deadline exceeded waiting for refresh")
        try:
            references = {}
            for currency in currencies:
                remaining_budget()
                cached = self._cache.get(f"{_CACHE_PREFIX}:{currency}")
                if (
                    cached is not None
                    and cached.currency == currency
                    and 0 <= (self._today() - cached.as_of).days <= self._max_age_days
                ):
                    references[currency] = cached
            if (
                len(references) == len(currencies)
                and len({r.as_of for r in references.values()}) == 1
            ):
                return references
            fetched = self._fetch_reference_rates(currencies)
            for reference in fetched.values():
                self._assert_fresh(reference)
            if len({r.as_of for r in fetched.values()}) > 1:
                raise MarketDataError("ECB returned inconsistent observation dates")
            if currencies.issubset(fetched):
                for currency in currencies:
                    remaining_budget()
                    self._cache.set(f"{_CACHE_PREFIX}:{currency}", fetched[currency])
            return fetched
        finally:
            self._fetch_lock.release()

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
                response = provider_get(
                    self._client,
                    f"{_BASE_URL}/{series}",
                    params={
                        "lastNObservations": 1,
                        "detail": "dataonly",
                        "format": "csvdata",
                    },
                    headers={"Accept": "text/csv"},
                    timeout=self._timeout,
                )
                if response.status_code == 404:
                    return {}
                response.raise_for_status()
                return self._parse_csv(response.text, currencies)
            except (
                csv.Error,
                httpx.HTTPError,
                InvalidOperation,
                KeyError,
                TypeError,
                ValueError,
            ) as exc:
                last_error = safe_error(exc)
                logger.warning(
                    "ECB FX fetch attempt %d/%d failed: %s", attempt, _RETRIES, last_error
                )
                if not retryable(exc) or attempt == _RETRIES:
                    break
                retry_pause(_RETRY_DELAY)
        raise MarketDataError(f"Could not fetch ECB rates after {attempt} attempts: {last_error}.")

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
            if (current := parsed.get(currency)) is None or candidate.as_of > current.as_of:
                parsed[currency] = candidate
        return parsed
