"""OpenTelemetry metrics and traces setup."""

from urllib.parse import unquote

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.market_data.instrumented_provider import FETCH_DURATION_METRIC

_FETCH_DURATION_BUCKETS = [0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 2.0, 5.0]


def _parse_headers(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    headers: dict[str, str] = {}
    for item in raw.split(","):
        k, _, v = item.partition("=")
        if k.strip():
            headers[k.strip()] = unquote(v.strip())
    return headers


def setup_telemetry(
    service_name: str,
    endpoint: str,
    export_interval_ms: int,
    headers_raw: str | None = None,
    *,
    register_global: bool = True,
) -> tuple[MeterProvider, TracerProvider, LoggerProvider]:
    resource = Resource.create({SERVICE_NAME: service_name})
    parsed_headers = _parse_headers(headers_raw)

    metric_exporter = OTLPMetricExporter(
        endpoint=f"{endpoint}/v1/metrics",
        headers=parsed_headers,
    )
    reader = PeriodicExportingMetricReader(
        metric_exporter, export_interval_millis=export_interval_ms
    )
    views = [
        View(
            instrument_name=FETCH_DURATION_METRIC,
            aggregation=ExplicitBucketHistogramAggregation(_FETCH_DURATION_BUCKETS),
        )
    ]
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader], views=views)
    if register_global:
        metrics.set_meter_provider(meter_provider)

    span_exporter = OTLPSpanExporter(
        endpoint=f"{endpoint}/v1/traces",
        headers=parsed_headers,
    )
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    if register_global:
        trace.set_tracer_provider(tracer_provider)

    log_exporter = OTLPLogExporter(
        endpoint=f"{endpoint}/v1/logs",
        headers=parsed_headers,
    )
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
    if register_global:
        set_logger_provider(logger_provider)

    return meter_provider, tracer_provider, logger_provider
