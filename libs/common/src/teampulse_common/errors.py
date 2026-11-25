"""Global exception handling — every error leaves a service as RFC 7807 ``application/problem+json``."""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from teampulse_common.logging import request_id_var
from teampulse_common.middleware import SECURITY_HEADERS

logger = logging.getLogger("teampulse.errors")
PROBLEM_JSON = "application/problem+json"
PROBLEM_BASE = "https://docs.teampulse.io/problems/"


class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"
    title: str = "Internal Server Error"

    def __init__(
        self,
        detail: str | None = None,
        *,
        code: str | None = None,
        errors: list[dict[str, Any]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail or self.title)
        self.detail = detail or self.title
        if code:
            self.code = code
        self.errors = errors
        self.headers = headers


class BadRequestError(AppError):
    status_code, code, title = 400, "bad_request", "Bad Request"


class UnauthorizedError(AppError):
    status_code, code, title = 401, "unauthorized", "Unauthorized"

    def __init__(self, detail: str | None = None, **kwargs: Any) -> None:
        kwargs.setdefault("headers", {"WWW-Authenticate": "Bearer"})
        super().__init__(detail, **kwargs)


class ForbiddenError(AppError):
    status_code, code, title = 403, "forbidden", "Forbidden"


class NotFoundError(AppError):
    status_code, code, title = 404, "not_found", "Not Found"


class ConflictError(AppError):
    status_code, code, title = 409, "conflict", "Conflict"


class PayloadTooLargeError(AppError):
    status_code, code, title = 413, "payload_too_large", "Payload Too Large"


class UnprocessableError(AppError):
    status_code, code, title = 422, "validation_failed", "Unprocessable Entity"


class LockedError(AppError):
    status_code, code, title = 423, "locked", "Locked"


class TooManyRequestsError(AppError):
    status_code, code, title = 429, "rate_limited", "Too Many Requests"


class ServiceUnavailableError(AppError):
    status_code, code, title = 503, "dependency_unavailable", "Service Unavailable"


def request_id_for(request: Request) -> str | None:
    """The current request id: from the context variable, or from the copy that
    ``RequestContextMiddleware`` keeps in the scope (the 500 handler runs outside the middleware)."""
    state = request.scope.get("state")
    return request_id_var.get() or (state.get("request_id") if isinstance(state, dict) else None)


def problem_response(
    request: Request,
    *,
    status: int,
    title: str,
    detail: str,
    code: str,
    errors: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"{PROBLEM_BASE}{code}",
        "title": title,
        "status": status,
        "detail": detail,
        "code": code,
        "instance": request.url.path,
        "request_id": request_id_for(request),
    }
    if errors:
        body["errors"] = errors
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON, headers=headers)


def _validation_errors(exc: RequestValidationError) -> list[dict[str, Any]]:
    out = []
    for err in exc.errors():
        loc = [str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path")]
        out.append({"field": ".".join(loc) or None, "message": err.get("msg"), "type": err.get("type")})
    return out


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error("request.failed", extra={"error_code": exc.code, "detail": exc.detail})
        return problem_response(
            request,
            status=exc.status_code,
            title=exc.title,
            detail=exc.detail,
            code=exc.code,
            errors=exc.errors,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return problem_response(
            request,
            status=422,
            title="Unprocessable Entity",
            detail="Request validation failed",
            code="validation_failed",
            errors=_validation_errors(exc),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        title = HTTPStatus(exc.status_code).phrase
        return problem_response(
            request,
            status=exc.status_code,
            title=title,
            detail=str(exc.detail) if exc.detail else title,
            code=title.lower().replace(" ", "_"),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        request_id = request_id_for(request)
        logger.exception(
            "request.unhandled_exception", extra={"path": request.url.path, "request_id": request_id}
        )
        # This response skips RequestContextMiddleware's send wrapper, so add its headers here too.
        headers = {name.decode(): value.decode() for name, value in SECURITY_HEADERS}
        headers["Cache-Control"] = "no-store"
        if request_id:
            headers["X-Request-ID"] = request_id
        return problem_response(
            request,
            status=500,
            title="Internal Server Error",
            detail="An unexpected error occurred. Quote the request_id when reporting it.",
            code="internal_error",
            headers=headers,
        )
