"""HTTP retry helpers built on tenacity."""

from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

P = ParamSpec("P")
T = TypeVar("T")


def async_http_retry(
    max_attempts: int = 3,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    return retry(
        reraise=True,
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError)),
        before_sleep=lambda rs: None,
    )
