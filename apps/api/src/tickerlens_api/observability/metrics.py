from __future__ import annotations

from fastapi import FastAPI

from tickerlens_api.settings import settings


def init_metrics(app: FastAPI) -> None:
    if not settings.metrics_enabled:
        return

    try:
        from prometheus_fastapi_instrumentator import Instrumentator
    except Exception:
        # Metrics are optional; don't fail app startup if dependency isn't installed.
        return

    Instrumentator().instrument(app).expose(
        app,
        endpoint=settings.metrics_path,
        include_in_schema=False,
    )

