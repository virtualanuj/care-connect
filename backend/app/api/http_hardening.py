"""Cross-cutting HTTP concerns: request ids, structured access log, security headers, size limit.

The access log records the method, the path (never the query string, which can hold a phone
number) and timing only, so it is safe to ship anywhere.
"""

import json
import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.domain.errors import ErrorCode

access_logger = logging.getLogger("careconnect.access")

_REQUEST_ID = re.compile(r"[A-Za-z0-9-]{8,64}")
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}

Next = Callable[[Request], Awaitable[Response]]


def configure_logging() -> None:
    """Send the access log to stdout as bare JSON lines (once, however often this is called)."""
    logger = logging.getLogger("careconnect")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)


def _request_id(request: Request) -> str:
    incoming = request.headers.get("X-Request-ID", "")
    return incoming if _REQUEST_ID.fullmatch(incoming) else str(uuid.uuid4())


def install_http_hardening(app: FastAPI, max_request_bytes: int) -> None:
    @app.middleware("http")
    async def harden(request: Request, call_next: Next) -> Response:
        request_id = _request_id(request)
        started = time.perf_counter()
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > max_request_bytes:
            response: Response = JSONResponse(
                status_code=413,
                content={
                    "code": ErrorCode.VALIDATION_ERROR.value,
                    "message": "Request body too large",
                },
            )
        else:
            response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        for name, value in _SECURITY_HEADERS.items():
            response.headers[name] = value
        access_logger.info(
            json.dumps(
                {
                    "requestId": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "durationMs": round((time.perf_counter() - started) * 1000, 1),
                }
            )
        )
        return response
