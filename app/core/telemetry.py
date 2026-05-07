"""OpenTelemetry metrics setup."""

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource, SERVICE_NAME


def setup_telemetry(
    service_name: str,
    endpoint: str,
    export_interval_ms: int,
) -> MeterProvider:
    resource = Resource.create({SERVICE_NAME: service_name})
    # SDK auto-config appends the signal path, but the explicit `endpoint` kwarg
    # is used verbatim - so we append /v1/metrics ourselves.
    exporter = OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics")
    reader = PeriodicExportingMetricReader(
        exporter, export_interval_millis=export_interval_ms
    )
    provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(provider)
    return provider
