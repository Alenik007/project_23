"""Фасад «движка» генерации: реальная Peft-модель из MODEL_PATH или заглушка."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from app import config

if TYPE_CHECKING:
    from app.inference import TextGenerator

logger = logging.getLogger(__name__)


class GenerationEngine(ABC):
    """Единый интерфейс для /generate."""

    @abstractmethod
    def generate(self, prompt: str, max_tokens: int) -> tuple[str, int]:
        """Возвращает (текст ответа, число сгенерированных токенов)."""

    @property
    @abstractmethod
    def model_display_name(self) -> str:
        """Имя модели для JSON-ответа."""


class StubEngine(GenerationEngine):
    """Лёгкий режим без torch (CI, пустой MODEL_PATH)."""

    @property
    def model_display_name(self) -> str:
        return config.MODEL_NAME

    def generate(self, prompt: str, max_tokens: int) -> tuple[str, int]:
        text = (
            f"[stub:{config.MODEL_NAME}] Краткий ответ на запрос "
            f"(первые символы промпта): {prompt[:120]!r}…"
        )
        if max_tokens < len(text):
            text = text[:max_tokens]
        approx_tokens = max(1, len(text) // 4)
        return text, approx_tokens


class PeftEngine(GenerationEngine):
    """Обёртка над TextGenerator из inference."""

    def __init__(self, gen: TextGenerator) -> None:
        self._gen = gen

    @property
    def model_display_name(self) -> str:
        return config.MODEL_NAME

    def generate(self, prompt: str, max_tokens: int) -> tuple[str, int]:
        text, n_new = self._gen.generate(prompt, max_new_tokens=max_tokens)
        return text, max(1, n_new)


def _adapter_ready(path: Path) -> bool:
    if not path.is_dir():
        return False
    return (path / "adapter_config.json").is_file() or any(path.glob("adapter_model.*"))


def load_engine() -> GenerationEngine:
    """Выбирает заглушку или реальную модель по MODEL_PATH / USE_STUB."""
    if config.USE_STUB:
        logger.info("USE_STUB=1 — используется заглушка генерации.")
        return StubEngine()

    adapter_root = Path(config.MODEL_PATH).expanduser().resolve()
    if not _adapter_ready(adapter_root):
        logger.warning(
            "В %s нет адаптера — используется заглушка. Задайте веса или HF_WEIGHTS_REPO.",
            adapter_root,
        )
        return StubEngine()

    from app.inference import load_generator_from_env

    gen = load_generator_from_env()
    return PeftEngine(gen)
