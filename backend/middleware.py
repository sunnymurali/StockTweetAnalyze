"""
HTTP request/response logging middleware.
- Assigns a short request ID (8-hex) to every request
- Logs method, path, status, duration
- Attaches X-Request-ID response header
- Logs 4xx/5xx at WARNING/ERROR level
"""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("http.access")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = uuid.uuid4().hex[:8]
        request.state.request_id = req_id
        t0 = time.perf_counter()

        # Log incoming request
        logger.debug(
            "→ %s %s  req=%s",
            request.method, request.url.path, req_id,
            extra={"request_id": req_id, "method": request.method, "path": request.url.path},
        )

        try:
            response = await call_next(request)
        except Exception:
            ms = round((time.perf_counter() - t0) * 1000)
            logger.exception(
                "✗ %s %s  UNHANDLED  [%dms]  req=%s",
                request.method, request.url.path, ms, req_id,
                extra={"request_id": req_id, "duration_ms": ms, "status_code": 500},
            )
            raise

        ms  = round((time.perf_counter() - t0) * 1000)
        sc  = response.status_code

        if sc >= 500:
            lvl, icon = logging.ERROR,   "✗"
        elif sc >= 400:
            lvl, icon = logging.WARNING, "⚠"
        else:
            lvl, icon = logging.INFO,    "✓"

        logger.log(
            lvl,
            "%s %s %s → %d  [%dms]  req=%s",
            icon, request.method, request.url.path, sc, ms, req_id,
            extra={
                "request_id": req_id,
                "method":     request.method,
                "path":       request.url.path,
                "status_code": sc,
                "duration_ms": ms,
            },
        )

        response.headers["X-Request-ID"] = req_id
        return response
