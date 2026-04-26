"""Базовая проверка промпта на типичные паттерны prompt injection."""

from __future__ import annotations

from fastapi import HTTPException

# Подстроки (нижний регистр), при совпадении промпт отклоняется.
INJECTION_PATTERNS: tuple[str, ...] = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "system:",
    "assistant:",
    "developer:",
    "you are now",
    "act as",
    "forget previous instructions",
    "disregard previous instructions",
)

INJECTION_REJECT_MESSAGE = "Prompt rejected due to suspicious instruction pattern"


def assert_prompt_not_injection(prompt: str) -> None:
    """Если в промпте найден подозрительный паттерн — HTTP 400."""
    lowered = prompt.lower()
    for pattern in INJECTION_PATTERNS:
        if pattern in lowered:
            raise HTTPException(status_code=400, detail=INJECTION_REJECT_MESSAGE)
