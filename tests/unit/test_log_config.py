"""Unit tests for the JSON logging formatter."""

import json
import logging

from app.core.log_config import _JsonFormatter


def _format(record: logging.LogRecord) -> dict:
    return json.loads(_JsonFormatter().format(record))


def _make_record(level: int = logging.INFO, msg: str = "hello", **extra) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test", level=level, pathname=__file__, lineno=10,
        msg=msg, args=(), exc_info=None,
    )
    for k, v in extra.items():
        setattr(record, k, v)
    return record


def test_basic_fields_present():
    out = _format(_make_record())
    assert out["level"] == "INFO"
    assert out["logger"] == "test"
    assert out["msg"] == "hello"
    assert "ts" in out


def test_timestamp_iso_format_with_milliseconds():
    out = _format(_make_record())
    assert out["ts"].endswith("Z")
    assert "T" in out["ts"]
    assert "." in out["ts"]


def test_extra_fields_are_included():
    out = _format(_make_record(http_status=200, http_duration_ms=42.0))
    assert out["http_status"] == 200
    assert out["http_duration_ms"] == 42.0


def test_standard_logrecord_attrs_not_leaked():
    out = _format(_make_record())
    assert "pathname" not in out
    assert "lineno" not in out
    assert "args" not in out


def test_exception_info_included_when_present():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys
        exc_info = sys.exc_info()
    record = logging.LogRecord(
        name="test", level=logging.ERROR, pathname=__file__, lineno=10,
        msg="failed", args=(), exc_info=exc_info,
    )
    out = _format(record)
    assert "exc" in out
    assert "ValueError" in out["exc"]
    assert "boom" in out["exc"]


def test_trace_context_injected_when_span_active():
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider

    tp = TracerProvider()
    trace.set_tracer_provider(tp)
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span("test-span"):
        out = _format(_make_record())

    assert "trace_id" in out
    assert "span_id" in out
    assert len(out["trace_id"]) == 32
    assert len(out["span_id"]) == 16

    tp.shutdown()
    trace._TRACER_PROVIDER = None


def test_trace_context_absent_when_no_span():
    from opentelemetry import trace
    trace._TRACER_PROVIDER = None
    out = _format(_make_record())
    assert "trace_id" not in out
    assert "span_id" not in out
