from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator

from tickerlens_api.settings import settings


@contextmanager
def start_span(name: str, **attributes) -> Iterator[object | None]:
    """
    Safe span helper.

    - No-op if OTel disabled or deps missing.
    - Avoids requiring callers to guard instrumentation code.
    """

    if not settings.otel_enabled:
        yield None
        return

    try:
        from opentelemetry import trace  # type: ignore

        tracer = trace.get_tracer("tickerlens")
        with tracer.start_as_current_span(name) as span:
            try:
                for k, v in attributes.items():
                    if v is None:
                        continue
                    span.set_attribute(k, v)
            except Exception:
                pass
            yield span
        return
    except Exception:
        yield None

