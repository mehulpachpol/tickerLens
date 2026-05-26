from __future__ import annotations

from fastapi import FastAPI

from tickerlens_api.settings import settings


def init_tracing(app: FastAPI) -> None:
    """
    Lightweight OpenTelemetry tracing bootstrap.

    - FastAPI spans
    - SQLAlchemy spans (DB)
    - httpx spans (outbound HTTP calls)

    Export:
    - OTLP/HTTP to a collector if `TICKERLENS_OTEL_OTLP_ENDPOINT` is set
    - otherwise, no-op (keeps startup cheap by default)
    """

    if not settings.otel_enabled:
        return
    if not settings.otel_otlp_endpoint:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except Exception:
        return

    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(endpoint=settings.otel_otlp_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor().instrument_app(app)

    # Instrument DB + outbound HTTP.
    from tickerlens_api.db.session import engine

    SQLAlchemyInstrumentor().instrument(engine=engine)
    HTTPXClientInstrumentor().instrument()

