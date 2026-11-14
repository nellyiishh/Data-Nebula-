from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger("errors")


class ErrorCode(StrEnum):
    """Stable error codes. The web app may branch on these, so never rename one."""

    REQUEST_INVALID = "request.invalid"
    ROUTE_NOT_FOUND = "route.not_found"
    METHOD_NOT_ALLOWED = "route.method_not_allowed"
    HTTP_ERROR = "http.error"
    SITE_NOT_FOUND = "site.not_found"
    DATE_NOT_FOUND = "date.not_found"
    LAYER_NOT_FOUND = "layer.not_found"
    POINT_OUTSIDE_SITE = "point.outside_site"
    INTERNAL = "internal.error"


class DomainError(Exception):
    status_code = 400

    def __init__(
        self, code: ErrorCode, message: str, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class NotFoundError(DomainError):
    status_code = 404


class UnprocessableError(DomainError):
    status_code = 422


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody


def _error_response(
    status_code: int, code: ErrorCode, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details or {}))
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body))


def _http_code(status_code: int) -> ErrorCode:
    if status_code == 404:
        return ErrorCode.ROUTE_NOT_FOUND
    if status_code == 405:
        return ErrorCode.METHOD_NOT_ALLOWED
    return ErrorCode.HTTP_ERROR


def register_error_handlers(app: FastAPI) -> None:
    """Every error leaves the API as {"error": {"code", "message", "details"}}."""

    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError) -> JSONResponse:
        return _error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = {"errors": jsonable_encoder(exc.errors(), exclude={"ctx", "input", "url"})}
        return _error_response(422, ErrorCode.REQUEST_INVALID, "Request is not valid.", details)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error_response(exc.status_code, _http_code(exc.status_code), str(exc.detail))

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error", exc_info=exc)
        return _error_response(500, ErrorCode.INTERNAL, "Something went wrong on the server.")
