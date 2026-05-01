"""Narrow retry helper. Retry only transient errors. Fail fast on bad input.

Pattern: borrowed from cost-aware-llm-pipeline skill.
"""
from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


# Names of provider-specific error classes we treat as retryable.
# We match by class name to avoid hard imports of either SDK.
_RETRYABLE_NAMES = {
    # Anthropic
    "APIConnectionError",
    "APITimeoutError",
    "InternalServerError",
    "RateLimitError",
    # Google
    "ServiceUnavailable",
    "DeadlineExceeded",
    "ResourceExhausted",
}


def is_retryable(exc: BaseException) -> bool:
    return type(exc).__name__ in _RETRYABLE_NAMES


def call_with_retry(
    func: Callable[[], T], *, max_attempts: int = 3, base_delay_s: float = 1.0
) -> T:
    """Run `func`; retry only on known transient errors with exponential backoff."""
    last: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as exc:  # noqa: BLE001 — we re-raise below if non-retryable
            last = exc
            if not is_retryable(exc) or attempt == max_attempts - 1:
                raise
            time.sleep(base_delay_s * (2**attempt))
    # Unreachable, but keeps type checkers happy.
    assert last is not None
    raise last
