from __future__ import annotations

import time
import uuid
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


_logger = logging.getLogger("tickerlens.access")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id

        t0 = time.perf_counter()
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = str(int((time.perf_counter() - t0) * 1000))

        try:
            user_id = getattr(request.state, "user_id", None)
            trace_id = None
            try:
                from opentelemetry import trace as _trace  # type: ignore

                span = _trace.get_current_span()
                ctx = span.get_span_context() if span else None
                if ctx and getattr(ctx, "trace_id", 0):
                    trace_id = f"{ctx.trace_id:032x}"
            except Exception:
                trace_id = None

            if trace_id:
                response.headers["X-Trace-ID"] = trace_id
            _logger.info(
                "request",
                extra={
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "user_id": user_id,
                },
            )
        except Exception:
            pass

        return response
