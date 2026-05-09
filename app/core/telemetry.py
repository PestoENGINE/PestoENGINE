"""OpenTelemetry metrics setup."""

from urllib.parse import unquote

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import Resource, SERVICE_NAME

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
) -> MeterProvider:
    resource = Resource.create({SERVICE_NAME: service_name})
    # SDK auto-config appends the signal path, but the explicit `endpoint` kwarg
    # is used verbatim - so we append /v1/metrics ourselves.
    exporter = OTLPMetricExporter(
        endpoint=f"{endpoint}/v1/metrics",
        headers=_parse_headers(headers_raw),
    )
    reader = PeriodicExportingMetricReader(
        exporter, export_interval_millis=export_interval_ms
    )
    views = [
        View(
            instrument_name="pestoengine_market_fetch_duration_seconds",
            aggregation=ExplicitBucketHistogramAggregation(_FETCH_DURATION_BUCKETS),
        )
    ]
    provider = MeterProvider(resource=resource, metric_readers=[reader], views=views)
    metrics.set_meter_provider(provider)
    return provider
