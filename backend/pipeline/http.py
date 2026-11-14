"""One HTTP call with retries for the busy public services the pipeline uses
(OpenStreetMap Overpass, NASA LP DAAC). Pipeline-only: the API never calls out."""

import time
from collections.abc import Callable
from typing import Any

from app.core.logging import get_logger

# These answers mean "busy, try again shortly"; anything else is returned as it is.
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
RETRY_WAITS_S = (5, 15, 30)
log = get_logger("http")


def request_with_retry(
    method: str,
    url: str,
    *,
    waits: tuple[float, ...] = RETRY_WAITS_S,
    sleep: Callable[[float], None] = time.sleep,
    **kwargs: Any,
) -> Any:
    """requests.request with retries on busy answers and dropped connections.
    The last answer is returned unchecked; callers decide what is an error."""
    import requests

    for wait in (*waits, None):
        try:
            response = requests.request(method, url, **kwargs)
        except (requests.ConnectionError, requests.Timeout) as exc:
            if wait is None:
                raise
            log.warning("%s %s failed (%s); retrying in %gs", method, _host(url), exc, wait)
        else:
            if response.status_code not in RETRY_STATUSES or wait is None:
                return response
            log.warning("%s answered %d; retrying in %gs", _host(url), response.status_code, wait)
        sleep(wait)
    raise AssertionError("unreachable")


def _host(url: str) -> str:
    return url.split("/")[2] if "//" in url else url
