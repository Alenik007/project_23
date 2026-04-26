"""Тесты Pydantic-валидации и успешного ответа /generate."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.model import StubEngine


def test_generate_success(stub_engine_client: TestClient):
    r = stub_engine_client.post(
        "/generate",
        json={"prompt": "Hello", "max_tokens": 256, "temperature": 0.7},
    )
    assert r.status_code == 200
    data = r.json()
    assert "result" in data and data["result"]
    assert data["max_tokens"] == 256
    assert data["temperature"] == 0.7


def test_generate_empty_prompt_422(stub_engine_client: TestClient):
    r = stub_engine_client.post(
        "/generate",
        json={"prompt": "", "max_tokens": 256, "temperature": 0.7},
    )
    assert r.status_code == 422


def test_generate_prompt_over_2000_chars_422(stub_engine_client: TestClient):
    r = stub_engine_client.post(
        "/generate",
        json={"prompt": "a" * 2001, "max_tokens": 256, "temperature": 0.7},
    )
    assert r.status_code == 422


def test_generate_temperature_out_of_range_422(stub_engine_client: TestClient):
    r = stub_engine_client.post(
        "/generate",
        json={"prompt": "ok", "max_tokens": 256, "temperature": 3.0},
    )
    assert r.status_code == 422


def test_generate_whitespace_only_prompt_422(stub_engine_client: TestClient):
    r = stub_engine_client.post("/generate", json={"prompt": "   \n\t  "})
    assert r.status_code == 422


def test_generate_503_when_no_engine(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.main.load_engine", lambda: StubEngine())
    from app.main import app

    with TestClient(app) as c:
        c.app.state.engine = None
        c.app.state.load_error = "нет движка"
        r = c.post("/generate", json={"prompt": "hi"})
    assert r.status_code == 503


def test_generate_invalid_prompt_type_422(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.main.load_engine", lambda: StubEngine())
    from app.main import app

    with TestClient(app) as c:
        r = c.post(
            "/generate",
            content=json.dumps({"prompt": 123}),
            headers={"Content-Type": "application/json"},
        )
    assert r.status_code == 422


def test_health_ok(stub_engine_client: TestClient):
    r = stub_engine_client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_root_ok(stub_engine_client: TestClient):
    r = stub_engine_client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data["service"] == "GenAI API"
    assert data["version"] == "1.0.0"
