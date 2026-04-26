"""Тесты rate limiting (slowapi)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_rate_limit_returns_429_after_ten_requests(stub_engine_client: TestClient):
    payload = {"prompt": "rate test", "max_tokens": 32, "temperature": 0.5}
    for i in range(10):
        r = stub_engine_client.post("/generate", json=payload)
        assert r.status_code == 200, f"request {i + 1} expected 200, got {r.status_code}: {r.text}"

    r11 = stub_engine_client.post("/generate", json=payload)
    assert r11.status_code == 429
    body = r11.json()
    assert "detail" in body
    assert "10" in body["detail"] or "rate" in body["detail"].lower()
