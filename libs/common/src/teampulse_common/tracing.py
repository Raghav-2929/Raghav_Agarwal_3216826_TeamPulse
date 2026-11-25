"""Distributed tracing with OpenTelemetry (OTLP → Jaeger locally, → ADOT/X-Ray in AWS).

Enabled only when ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set, so tests and the zero-infra local mode pay
nothing. FastAPI server spans and httpx client spans are created automatically and the W3C
``traceparent`` header is propagated between services.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from teampulse_common.settings import ServiceSettings

logger = logging.getLogger("teampulse.tracing")
_httpx_instrumented = False


def setup_tracing(app: FastAPI, settings: ServiceSettings) -> None:
    global _httpx_instrumented
    if not settings.otel_exporter_otlp_endpoint:
        return
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": settings.service_name,
                "service.version": settings.service_version,
                "deployment.environment": settings.environment,
            }
        )
    )
    endpoint = settings.otel_exporter_otlp_endpoint.rstrip("/") + "/v1/traces"
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, excluded_urls="health/.*", tracer_provider=provider)
    if not _httpx_instrumented:
        HTTPXClientInstrumentor().instrument(tracer_provider=provider)
        _httpx_instrumented = True
    logger.info("tracing.enabled", extra={"endpoint": endpoint})
