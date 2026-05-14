"""OpenTelemetry metrics and traces setup."""

from urllib.parse import unquote

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.market_data.instrumented_provider import FETCH_DURATION_METRIC

_FETCH_DURATION_BUCKETS = [0.1, 0.25, 0.5, 0.75, 1.0, 2.0, 5.0]


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
) -> tuple[MeterProvider, TracerProvider]:
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
    metrics.set_meter_provider(meter_provider)

    span_exporter = OTLPSpanExporter(
        endpoint=f"{endpoint}/v1/traces",
        headers=parsed_headers,
    )
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(tracer_provider)

    return meter_provider, tracer_provider
