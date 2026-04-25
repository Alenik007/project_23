"""Тесты API без загрузки реальных весов (заглушка через патч load_engine)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.model import StubEngine


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.main.load_engine", lambda: StubEngine())
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_health_ok(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_root_ok(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data["service"] == "GenAI API"
    assert data["version"] == "1.0.0"
    assert data["description"] == "Fine-tuned LLM inference API"


def test_generate_ok(client: TestClient):
    r = client.post("/generate", json={"prompt": "  hello  ", "max_tokens": 64})
    assert r.status_code == 200
    data = r.json()
    assert data["prompt"] == "hello"
    assert "response" in data and data["response"]
    assert "model" in data and data["model"]
    assert isinstance(data["tokens_used"], int)
    assert data["tokens_used"] >= 1


def test_generate_empty_prompt_422(client: TestClient):
    r = client.post("/generate", json={"prompt": ""})
    assert r.status_code == 422


def test_generate_whitespace_only_422(client: TestClient):
    r = client.post("/generate", json={"prompt": "   \n\t  "})
    assert r.status_code == 422


def test_generate_503_when_no_engine():
    from app.main import app

    with TestClient(app) as c:
        c.app.state.engine = None
        c.app.state.load_error = "нет движка"
        r = c.post("/generate", json={"prompt": "hi"})
    assert r.status_code == 503


def test_generate_invalid_type_422(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.main.load_engine", lambda: StubEngine())
    from app.main import app

    with TestClient(app) as c:
        r = c.post(
            "/generate",
            content=json.dumps({"prompt": 123}),
            headers={"Content-Type": "application/json"},
        )
    assert r.status_code == 422


def test_stub_engine_returns_tokens():
    eng = StubEngine()
    text, n = eng.generate("abc", 256)
    assert "abc" in text or "stub" in text.lower()
    assert n >= 1
