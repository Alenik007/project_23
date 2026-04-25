#!/usr/bin/env python3
"""
Загрузка весов адаптера в MODEL_PATH (вне репозитория, если веса > 500 МБ).

Источник: Hugging Face Hub (репозиторий задаётся HF_WEIGHTS_REPO).
Токен: HF_TOKEN (опционально, для приватных репозиториев).

Переменные окружения не хранятся в коде — только чтение из os.environ.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("download_weights")


def _default_model_path() -> Path:
    root = Path(__file__).resolve().parent.parent
    return root / "model_weights"


def _weights_already_present(target: Path) -> bool:
    if not target.is_dir():
        return False
    if (target / "adapter_config.json").is_file():
        return True
    return any(target.glob("adapter_model.*"))


def run_download() -> int:
    model_path = Path(os.environ.get("MODEL_PATH", str(_default_model_path()))).expanduser()
    model_path.mkdir(parents=True, exist_ok=True)

    if _weights_already_present(model_path):
        logger.info("Веса уже присутствуют в %s, загрузка пропущена.", model_path)
        return 0

    repo = os.environ.get("HF_WEIGHTS_REPO", "").strip()
    if not repo:
        logger.info(
            "HF_WEIGHTS_REPO не задан — пропуск загрузки. "
            "Положите адаптер в %s или задайте HF_WEIGHTS_REPO.",
            model_path,
        )
        return 0

    token = os.environ.get("HF_TOKEN", "").strip() or None

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        logger.error("Нужен пакет huggingface_hub: %s", exc)
        return 1

    logger.info("Скачивание %s -> %s", repo, model_path)
    snapshot_download(
        repo_id=repo,
        local_dir=str(model_path),
        token=token,
        resume_download=True,
    )
    logger.info("Готово.")
    return 0


def main() -> int:
    try:
        return run_download()
    except Exception:  # noqa: BLE001
        logger.exception("Ошибка загрузки весов")
        return 1


if __name__ == "__main__":
    sys.exit(main())
