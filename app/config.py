"""Настройки приложения из переменных окружения (без хардкода путей к весам в бизнес-логике)."""

from __future__ import annotations

import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _default_model_dir() -> str:
    return str(_ROOT / "model_weights")


MODEL_PATH = os.getenv("MODEL_PATH", _default_model_dir())
MODEL_NAME = os.getenv("MODEL_NAME", "local-finetuned-model")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
ENV = os.getenv("ENV", "development")

# Дообученный адаптер (LoRA) лежит в MODEL_PATH; базовая модель — с Hugging Face.
BASE_MODEL_NAME = os.getenv("BASE_MODEL_NAME", "Qwen/Qwen2.5-1.5B-Instruct").strip()
BASE_MODEL_REVISION = os.getenv("BASE_MODEL_REVISION", "main").strip()
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "").strip() or None

TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))
TOP_P = float(os.getenv("TOP_P", "0.9"))
DO_SAMPLE = os.getenv("DO_SAMPLE", "false").lower() in ("1", "true", "yes")

# Принудительная заглушка без torch (например, в облегчённых средах).
USE_STUB = os.getenv("USE_STUB", "").lower() in ("1", "true", "yes")

# Репозиторий HF со снапшотом весов в model_weights/ (см. scripts/download_weights.py).
HF_WEIGHTS_REPO = os.getenv("HF_WEIGHTS_REPO", "").strip()

# CORS: список origin через запятую (например: http://localhost:3000,https://app.vercel.app)
_DEFAULT_CORS = "http://localhost:3000"


def cors_allowed_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", _DEFAULT_CORS).strip()
    return [o.strip() for o in raw.split(",") if o.strip()]
