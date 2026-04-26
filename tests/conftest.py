"""Общие фикстуры: заглушка движка и сброс rate limit между тестами."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.model import StubEngine


@pytest.fixture(autouse=True)
def reset_rate_limit_storage() -> None:
    from app.rate_limiter import limiter

    try:
        limiter.reset()
    except Exception:
        pass
    yield
    try:
        limiter.reset()
    except Exception:
        pass


@pytest.fixture
def stub_engine_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.main.load_engine", lambda: StubEngine())
    from app.main import app

    with TestClient(app) as client:
        yield client
