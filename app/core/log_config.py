"""Logging configuration: JSON formatter with OTel trace context injection."""

import json
import logging
import re
import time
from urllib.parse import quote, unquote

from opentelemetry import trace

from app.core.config import Settings, get_settings

_STANDARD_LOGRECORD_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "taskName",
    }
)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info or record.exc_text:
            payload["exc"] = record.exc_text or self.formatException(record.exc_info)

        # Inject any extra fields passed via logger.info(..., extra={...}).
        # Skip standard LogRecord attributes to avoid noise.
        for key, value in record.__dict__.items():
            if key in _STANDARD_LOGRECORD_ATTRS or key.startswith("_"):
                continue
            payload[key] = value

        ctx = trace.get_current_span().get_span_context()
        if ctx.is_valid:
            payload["trace_id"] = format(ctx.trace_id, "032x")
            payload["span_id"] = format(ctx.span_id, "016x")

        return json.dumps(payload, ensure_ascii=False, default=str)


class SensitiveDataFilter(logging.Filter):
    """Redact provider keys and telemetry credentials before any owned export."""

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        secrets = [settings.alpha_vantage_api_key, settings.redis_url]
        for item in (settings.otel_exporter_otlp_headers or "").split(","):
            _, sep, value = item.partition("=")
            if sep and value.strip():
                secrets.extend([value.strip(), unquote(value.strip())])
        self._secrets = sorted(
            {v for secret in secrets if secret for v in (secret, quote(secret, safe=""))},
            key=len,
            reverse=True,
        )

    def redact(self, value: object) -> object:
        if isinstance(value, str):
            for secret in self._secrets:
                value = value.replace(secret, "[REDACTED]")
            return re.sub(
                r"(?i)((?:apikey|api_key|access_token)=)[^&\s\"']+", r"\1[REDACTED]", value
            )
        if isinstance(value, dict):
            return {k: self.redact(v) for k, v in value.items()}
        if isinstance(value, (tuple, list)):
            return [self.redact(v) for v in value]
        return value

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self.redact(record.getMessage())
        record.args = ()
        if record.exc_info:
            record.exc_text = str(self.redact(logging.Formatter().formatException(record.exc_info)))
            record.exc_info = None
        for key, value in list(record.__dict__.items()):
            if key not in {"msg", "args", "exc_info"}:
                record.__dict__[key] = self.redact(value)
        return True


def setup_logging(settings: Settings | None = None) -> SensitiveDataFilter:
    settings = settings or get_settings()
    redactor = SensitiveDataFilter(settings)
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "_pesto_console", False):
            root.removeHandler(handler)
            handler.close()
    handler = logging.StreamHandler()
    handler._pesto_console = True
    handler.setFormatter(_JsonFormatter())
    handler.addFilter(redactor)
    root.addHandler(handler)
    root.setLevel(settings.log_level)
    # Logger filtering also protects handlers installed by a hosting process.
    http_logger = logging.getLogger("httpx")
    for existing in list(http_logger.filters):
        if isinstance(existing, SensitiveDataFilter):
            http_logger.removeFilter(existing)
    http_logger.addFilter(redactor)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    return redactor
