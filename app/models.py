"""Pydantic-модели запросов и ответов для /generate."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="Текст запроса: не пустой после trim, до 2000 символов.")
    max_tokens: int = Field(default=256, ge=1, le=2048, description="Максимум новых токенов.")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Температура сэмплирования.")

    @field_validator("prompt", mode="before")
    @classmethod
    def _coerce_prompt(cls, v: object) -> str:
        if not isinstance(v, str):
            raise ValueError("Поле prompt должно быть строкой.")
        return v

    @field_validator("prompt")
    @classmethod
    def _prompt_nonempty_and_length(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Промпт не может быть пустым или состоять только из пробелов.")
        if len(s) > 2000:
            raise ValueError("Промпт не может быть длиннее 2000 символов.")
        return s


class GenerateSuccessResponse(BaseModel):
    result: str
    max_tokens: int
    temperature: float
