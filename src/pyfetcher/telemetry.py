"""OpenTelemetry traces and metrics for fetches and job execution.

Tempo is supported through its OTLP receiver; no Tempo-specific coupling is
required. Python logging remains standard logging with a filter that adds the
active trace and span IDs for correlation with a log backend such as Loki.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from time import perf_counter
from typing import Literal
from urllib.parse import urlsplit

try:
    from opentelemetry import metrics, propagate, trace
    from opentelemetry.metrics import Meter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.trace import SpanKind, Status, StatusCode, Tracer
except ImportError as exc:  # pragma: no cover - optional dependency
    raise ImportError("observability support requires `pip install 'fetchkit[observe]'`") from exc

from pyfetcher.contracts import FetchRequest, FetchResponse
from pyfetcher.jobs import JobRequest, JobResult, JobTraceContext


@dataclass(frozen=True, slots=True)
class TelemetryConfig:
    """OTLP exporter settings suitable for an OpenTelemetry Collector or Tempo."""

    service_name: str = "fetchkit"
    endpoint: str = "http://localhost:4317"
    protocol: Literal["grpc", "http/protobuf"] = "grpc"
    insecure: bool = True
    headers: Mapping[str, str] | None = None
    metric_export_interval_ms: int = 30_000


@dataclass(slots=True)
class TelemetryRuntime:
    """Configured providers with explicit flush and shutdown ownership."""

    tracer_provider: TracerProvider
    meter_provider: MeterProvider

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        traces = self.tracer_provider.force_flush(timeout_millis)
        metric_result = self.meter_provider.force_flush(timeout_millis)
        return bool(traces) and metric_result is not False

    def shutdown(self) -> None:
        self.meter_provider.shutdown()
        self.tracer_provider.shutdown()


def configure_telemetry(
    config: TelemetryConfig | None = None,
    *,
    set_global: bool = True,
) -> TelemetryRuntime:
    """Configure OTLP span and metric exporters.

    Point ``endpoint`` at an OpenTelemetry Collector or Tempo OTLP endpoint.
    Logs are correlated through :class:`TraceContextFilter` instead of relying
    on the still-evolving OpenTelemetry Python logs API.
    """
    resolved = config or TelemetryConfig()
    if resolved.protocol == "grpc":
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter,
        )
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        span_exporter = OTLPSpanExporter(
            endpoint=resolved.endpoint,
            insecure=resolved.insecure,
            headers=resolved.headers,
        )
        metric_exporter = OTLPMetricExporter(
            endpoint=resolved.endpoint,
            insecure=resolved.insecure,
            headers=resolved.headers,
        )
    else:
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
            OTLPMetricExporter,
        )
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        span_exporter = OTLPSpanExporter(
            endpoint=resolved.endpoint,
            headers=resolved.headers,
        )
        metric_exporter = OTLPMetricExporter(
            endpoint=resolved.endpoint,
            headers=resolved.headers,
        )

    resource = Resource.create({"service.name": resolved.service_name})
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    reader = PeriodicExportingMetricReader(
        metric_exporter,
        export_interval_millis=resolved.metric_export_interval_ms,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    if set_global:
        trace.set_tracer_provider(tracer_provider)
        metrics.set_meter_provider(meter_provider)
    return TelemetryRuntime(tracer_provider, meter_provider)


class TraceContextFilter(logging.Filter):
    """Attach active OTel identifiers to standard Python log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        context = trace.get_current_span().get_span_context()
        record.otel_trace_id = f"{context.trace_id:032x}" if context.is_valid else ""
        record.otel_span_id = f"{context.span_id:016x}" if context.is_valid else ""
        return True


def _parent_context(job: JobRequest):
    carrier = {
        key: value
        for key, value in {
            "traceparent": job.trace.traceparent,
            "tracestate": job.trace.tracestate,
            "baggage": ",".join(f"{k}={v}" for k, v in job.trace.baggage.items()) or None,
        }.items()
        if value is not None
    }
    return propagate.extract(carrier) if carrier else None


def _current_job_trace() -> JobTraceContext:
    carrier: dict[str, str] = {}
    propagate.inject(carrier)
    baggage = {
        key.strip(): value.strip()
        for item in carrier.get("baggage", "").split(",")
        if "=" in item
        for key, value in [item.split("=", 1)]
    }
    return JobTraceContext(
        traceparent=carrier.get("traceparent"),
        tracestate=carrier.get("tracestate"),
        baggage=baggage,
    )


class OpenTelemetryJobHook:
    """JobExecutor hook producing spans, metrics, and child propagation."""

    def __init__(self, *, tracer: Tracer | None = None, meter: Meter | None = None) -> None:
        self._tracer = tracer or trace.get_tracer("pyfetcher.jobs")
        resolved_meter = meter or metrics.get_meter("pyfetcher.jobs")
        self._started = resolved_meter.create_counter("fetchkit.jobs.started")
        self._completed = resolved_meter.create_counter("fetchkit.jobs.completed")
        self._duration = resolved_meter.create_histogram(
            "fetchkit.jobs.duration",
            unit="s",
        )

    async def __call__(
        self,
        job: JobRequest,
        call_next: Callable[[JobRequest], Awaitable[JobResult]],
    ) -> JobResult:
        attributes = {
            "fetchkit.job.template": job.template.key,
            "fetchkit.job.id": str(job.id),
            "fetchkit.flow.id": str(job.run_id),
            "fetchkit.job.attempt": job.attempt,
        }
        host = urlsplit(job.target).hostname if job.target else None
        if host:
            attributes["server.address"] = host
        started = perf_counter()
        self._started.add(1, attributes)
        with self._tracer.start_as_current_span(
            f"job {job.template.name}",
            context=_parent_context(job),
            kind=SpanKind.CONSUMER,
            attributes=attributes,
        ) as span:
            try:
                result = await call_next(job)
            except BaseException as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                raise
            status_attributes = {**attributes, "fetchkit.job.status": result.status}
            if result.status in {"failed", "cancelled"}:
                span.set_status(Status(StatusCode.ERROR, result.error or result.status))
            else:
                span.set_status(Status(StatusCode.OK))
            child_trace = _current_job_trace()
            if result.spawned_jobs:
                result = result.model_copy(
                    update={
                        "spawned_jobs": tuple(
                            child.model_copy(update={"trace": child_trace})
                            for child in result.spawned_jobs
                        )
                    }
                )
        self._duration.record(perf_counter() - started, status_attributes)
        self._completed.add(1, status_attributes)
        return result


class OpenTelemetryFetchMiddleware:
    """FetchService async middleware for client spans and HTTP metrics."""

    def __init__(self, *, tracer: Tracer | None = None, meter: Meter | None = None) -> None:
        self._tracer = tracer or trace.get_tracer("pyfetcher.fetch")
        resolved_meter = meter or metrics.get_meter("pyfetcher.fetch")
        self._requests = resolved_meter.create_counter("fetchkit.http.client.requests")
        self._duration = resolved_meter.create_histogram(
            "fetchkit.http.client.duration",
            unit="s",
        )

    async def __call__(
        self,
        request: FetchRequest,
        call_next: Callable[[FetchRequest], Awaitable[FetchResponse]],
    ) -> FetchResponse:
        parts = urlsplit(request.url.unicode_string())
        attributes: dict[str, str | int] = {
            "http.request.method": request.method,
            "url.scheme": parts.scheme,
            "server.address": parts.hostname or "",
            "fetchkit.http.backend": request.backend,
        }
        started = perf_counter()
        self._requests.add(1, attributes)
        with self._tracer.start_as_current_span(
            f"HTTP {request.method}",
            kind=SpanKind.CLIENT,
            attributes=attributes,
        ) as span:
            try:
                response = await call_next(request)
            except BaseException as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                raise
            attributes["http.response.status_code"] = response.status_code
            span.set_attribute("http.response.status_code", response.status_code)
            if response.status_code >= 400:
                span.set_status(Status(StatusCode.ERROR))
        self._duration.record(perf_counter() - started, attributes)
        return response


__all__ = [
    "OpenTelemetryFetchMiddleware",
    "OpenTelemetryJobHook",
    "TelemetryConfig",
    "TelemetryRuntime",
    "TraceContextFilter",
    "configure_telemetry",
]
