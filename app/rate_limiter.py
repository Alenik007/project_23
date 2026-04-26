"""Rate limiting для API (slowapi)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

RATE_LIMIT_MESSAGE = (
    "Rate limit exceeded: no more than 10 requests per minute per IP address are allowed."
)

limiter = Limiter(key_func=get_remote_address, auto_check=False)


def _rate_limit_exceeded(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    _ = request, exc
    return JSONResponse(
        status_code=429,
        content={"detail": RATE_LIMIT_MESSAGE},
    )


def register_rate_limiting(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded)
    app.add_middleware(SlowAPIMiddleware)
