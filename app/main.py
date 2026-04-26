"""FastAPI GenAI API: корневой маршрут, health и генерация."""

import asyncio
import logging
import os
import subprocess
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app import config
from app.model import GenerationEngine, load_engine
from app.models import GenerateRequest, GenerateSuccessResponse
from app.rate_limiter import limiter, register_rate_limiting
from app.security import assert_prompt_not_injection

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

register_rate_limiting(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _stream_text_as_word_chunks(text: str, delay_sec: float = 0.06) -> AsyncIterator[str]:
    """Потоковая отдача уже сгенерированного текста по словам (UX streaming).

    Нативный поток токенов из transformers здесь не используется: сначала полный
    ответ модели, затем нарезка по словам с небольшой паузой.
    """
    words = text.split()
    if not words:
        if text:
            yield text
        return
    for word in words:
        yield word + " "
        await asyncio.sleep(delay_sec)


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


@app.post("/generate", response_model=GenerateSuccessResponse)
@limiter.limit("10/minute")
async def generate(payload: GenerateRequest, request: Request) -> GenerateSuccessResponse:
    # 1) Pydantic уже проверил тело. 2) Базовая защита от prompt injection. 3) Rate limit.
    assert_prompt_not_injection(payload.prompt)
    limiter._check_request_limit(request, generate, in_middleware=False)

    engine: GenerationEngine | None = getattr(app.state, "engine", None)
    if engine is None:
        err = getattr(app.state, "load_error", None)
        raise HTTPException(
            status_code=503,
            detail=err or "Сервис не готов.",
        )

    text, _tokens_used = engine.generate(
        payload.prompt,
        payload.max_tokens,
        temperature=payload.temperature,
    )
    return GenerateSuccessResponse(
        result=text,
        max_tokens=payload.max_tokens,
        temperature=payload.temperature,
    )


@app.post("/generate/stream")
@limiter.limit("10/minute")
async def generate_stream(payload: GenerateRequest, request: Request) -> StreamingResponse:
    """Потоковая выдача ответа (text/plain): та же валидация, фильтр и rate limit, что и у /generate."""
    assert_prompt_not_injection(payload.prompt)
    limiter._check_request_limit(request, generate_stream, in_middleware=False)

    engine: GenerationEngine | None = getattr(app.state, "engine", None)
    if engine is None:
        err = getattr(app.state, "load_error", None)
        raise HTTPException(
            status_code=503,
            detail=err or "Сервис не готов.",
        )

    text, _tokens_used = await asyncio.to_thread(
        lambda: engine.generate(
            payload.prompt,
            payload.max_tokens,
            payload.temperature,
        ),
    )

    async def body() -> AsyncIterator[str]:
        async for chunk in _stream_text_as_word_chunks(text):
            yield chunk

    return StreamingResponse(
        body(),
        media_type="text/plain; charset=utf-8",
    )
