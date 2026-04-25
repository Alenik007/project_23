"""FastAPI GenAI API: корневой маршрут, health и генерация."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.model import GenerationEngine, load_engine

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

logger = logging.getLogger(__name__)


def _run_weight_download_script() -> None:
    script = _PROJECT_ROOT / "scripts" / "download_weights.py"
    if not script.is_file():
        return
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(_PROJECT_ROOT),
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.stdout:
        logger.info("download_weights stdout:\n%s", proc.stdout.strip())
    if proc.stderr:
        logger.warning("download_weights stderr:\n%s", proc.stderr.strip())
    if proc.returncode != 0:
        logger.warning("download_weights завершился с кодом %s", proc.returncode)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _run_weight_download_script()
    try:
        app.state.engine: GenerationEngine = load_engine()
        app.state.load_error = None
        logger.info("Движок генерации готов (%s).", type(app.state.engine).__name__)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Ошибка загрузки движка: %s", exc)
        app.state.engine = None
        app.state.load_error = str(exc)
    yield
    app.state.engine = None


app = FastAPI(
    title="GenAI API",
    description="Fine-tuned LLM inference API",
    version="1.0.0",
    lifespan=lifespan,
)


class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="Текст запроса, не пустой после trim, до 4096 символов.")
    max_tokens: int = Field(default=256, ge=1, le=2048, description="Максимум новых токенов.")

    @field_validator("prompt", mode="before")
    @classmethod
    def _coerce_str(cls, v: object) -> str:
        if not isinstance(v, str):
            raise ValueError("Поле prompt должно быть строкой.")
        return v

    @field_validator("prompt")
    @classmethod
    def _nonempty_and_len(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Промпт не может быть пустым.")
        if len(s) > 4096:
            raise ValueError("Промпт не может быть длиннее 4096 символов.")
        return s


class GenerateResponse(BaseModel):
    prompt: str
    response: str
    model: str
    tokens_used: int


@app.get("/")
async def root():
    return {
        "service": "GenAI API",
        "version": "1.0.0",
        "description": "Fine-tuned LLM inference API",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/generate", response_model=GenerateResponse)
async def generate(body: GenerateRequest) -> GenerateResponse:
    engine: GenerationEngine | None = getattr(app.state, "engine", None)
    if engine is None:
        err = getattr(app.state, "load_error", None)
        raise HTTPException(
            status_code=503,
            detail=err or "Сервис не готов.",
        )

    text, tokens_used = engine.generate(body.prompt.strip(), body.max_tokens)
    return GenerateResponse(
        prompt=body.prompt.strip(),
        response=text,
        model=engine.model_display_name,
        tokens_used=tokens_used,
    )
