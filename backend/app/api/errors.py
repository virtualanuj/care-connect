"""Exception handlers: every error body is exactly {code, message} (docs/openapi.yaml `Error`)."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.errors import DomainError, ErrorCode

logger = logging.getLogger(__name__)

_HTTP_STATUS_TO_CODE = {
    401: ErrorCode.UNAUTHENTICATED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    429: ErrorCode.RATE_LIMITED,
}
_HTTP_MESSAGES = {
    ErrorCode.UNAUTHENTICATED: "Authentication required",
    ErrorCode.FORBIDDEN: "Not permitted",
    ErrorCode.NOT_FOUND: "Resource not found",
    ErrorCode.RATE_LIMITED: "Too many requests",
    ErrorCode.VALIDATION_ERROR: "Invalid request",
}


def _body(status: int, code: ErrorCode, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"code": code.value, "message": message})


async def _domain_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    return _body(exc.status_code, exc.code, exc.message)


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # Report only field locations and rule names, never submitted values (may be PHI).
    problems = sorted(
        {
            f"{'.'.join(str(p) for p in e['loc'][1:]) or e['loc'][0]}: {e['type']}"
            for e in exc.errors()
        }
    )
    return _body(400, ErrorCode.VALIDATION_ERROR, "Invalid request: " + "; ".join(problems))


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = _HTTP_STATUS_TO_CODE.get(exc.status_code)
    if code is None:
        return _body(400, ErrorCode.VALIDATION_ERROR, _HTTP_MESSAGES[ErrorCode.VALIDATION_ERROR])
    return _body(exc.status_code, code, _HTTP_MESSAGES[code])


async def _unhandled_error(_: Request, exc: Exception) -> JSONResponse:
    # Log only the exception type: messages can contain patient data.
    logger.error("Unhandled exception of type %s", type(exc).__name__)
    return _body(500, ErrorCode.INTERNAL_ERROR, "Internal server error")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _domain_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(Exception, _unhandled_error)
