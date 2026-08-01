"""Unit tests for telemetry helpers."""

from opentelemetry.sdk._logs import LoggerProvider as SdkLoggerProvider
from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider

from app.core.telemetry import _parse_headers


def test_none_returns_empty():
    assert _parse_headers(None) == {}


def test_empty_string_returns_empty():
    assert _parse_headers("") == {}


def test_single_pair():
    assert _parse_headers("Foo=bar") == {"Foo": "bar"}


def test_multiple_pairs():
    assert _parse_headers("k1=v1,k2=v2") == {"k1": "v1", "k2": "v2"}


def test_url_encoded_value():
    assert _parse_headers("Authorization=Basic%20abc") == {"Authorization": "Basic abc"}


def test_base64_padding_equals_not_truncated():
    # partition("=") splits on first "=" only — trailing "==" in base64 must survive
    assert _parse_headers("Authorization=Basic%20abc==") == {"Authorization": "Basic abc=="}


def test_empty_key_skipped():
    assert _parse_headers("=orphanvalue") == {}


def test_empty_value_allowed():
    assert _parse_headers("k=") == {"k": ""}


def test_whitespace_around_key_and_value_stripped():
    assert _parse_headers(" k = v ") == {"k": "v"}


def test_grafana_cloud_header_roundtrip():
    raw = "Authorization=Basic%20MTYyOTMzMzpnbGNfZXlK"
    result = _parse_headers(raw)
    assert result == {"Authorization": "Basic MTYyOTMzMzpnbGNfZXlK"}


def test_setup_telemetry_returns_real_logger_provider():
    from app.core.telemetry import setup_telemetry

    mp, tp, lp = setup_telemetry("svc", "http://localhost:4318", 60_000)
    try:
        assert isinstance(lp, SdkLoggerProvider)
    finally:
        mp.shutdown()
        tp.shutdown()
        lp.shutdown()


def test_setup_telemetry_returns_real_tracer_provider():
    from app.core.telemetry import setup_telemetry

    mp, tp, lp = setup_telemetry("svc", "http://localhost:4318", 60_000)
    try:
        assert isinstance(tp, SdkTracerProvider)
    finally:
        mp.shutdown()
        tp.shutdown()
        lp.shutdown()
