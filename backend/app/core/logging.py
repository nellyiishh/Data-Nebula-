import logging
import re
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_request_id: ContextVar[str] = ContextVar("request_id", default="-")
_ROOT = "nebula"


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True


def configure_logging(level: str = "INFO") -> None:
    """Idempotent: safe to call from every entry point (API, pipeline scripts, tests)."""
    root = logging.getLogger(_ROOT)
    if root.handlers:
        return
    handler = logging.StreamHandler()
    handler.addFilter(_RequestIdFilter())
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s")
    )
    root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"{_ROOT}.{name}")


async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Reuse the caller's request ID (so web → API → logs share one) or mint a new one."""
    incoming = request.headers.get(REQUEST_ID_HEADER, "")
    request_id = incoming if _SAFE_REQUEST_ID.match(incoming) else uuid.uuid4().hex
    token = _request_id.set(request_id)
    try:
        response = await call_next(request)
    finally:
        _request_id.reset(token)
    response.headers[REQUEST_ID_HEADER] = request_id
    return response
