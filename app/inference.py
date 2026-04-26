"""Загрузка модели (один раз при старте) и синхронная генерация текста."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

from app import config

logger = logging.getLogger(__name__)

try:
    from transformers import BitsAndBytesConfig
except ImportError:  # pragma: no cover
    BitsAndBytesConfig = None  # type: ignore[misc, assignment]


def _resolve_adapter_path() -> Path:
    return Path(config.MODEL_PATH).expanduser().resolve()


def _adapter_dir_looks_valid(path: Path) -> bool:
    if not path.is_dir():
        return False
    return (path / "adapter_config.json").is_file() or any(path.glob("adapter_model.*"))


@dataclass
class GenerationConfig:
    max_new_tokens: int
    temperature: float
    top_p: float
    do_sample: bool


@dataclass
class ModelInfo:
    base_model_name: str
    adapter_path: str
    device: str


class TextGenerator:
    """Обёртка над tokenizer + PeftModel для однократной загрузки при старте."""

    def __init__(
        self,
        *,
        base_model_name: str,
        base_revision: str,
        adapter_path: Path,
        system_prompt: str | None,
        gen_cfg: GenerationConfig,
    ) -> None:
        self._system_prompt = (system_prompt or "").strip() or None
        self._default_gen_cfg = gen_cfg
        self._tokenizer = AutoTokenizer.from_pretrained(
            base_model_name,
            revision=base_revision,
            trust_remote_code=True,
        )
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token

        use_bnb_4bit = torch.cuda.is_available() and BitsAndBytesConfig is not None
        bnb = None
        if use_bnb_4bit:
            bnb = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
            )

        if not adapter_path.is_dir():
            raise FileNotFoundError(f"Каталог адаптера не найден: {adapter_path}")

        logger.info("Загрузка базовой модели %s (revision=%s)...", base_model_name, base_revision)
        base = AutoModelForCausalLM.from_pretrained(
            base_model_name,
            revision=base_revision,
            quantization_config=bnb if use_bnb_4bit else None,
            device_map="auto" if use_bnb_4bit else None,
            trust_remote_code=True,
        )
        if not use_bnb_4bit:
            base = base.to("cpu")

        logger.info("Подключение LoRA из %s", adapter_path)
        self._model = PeftModel.from_pretrained(base, str(adapter_path))
        self._device = next(self._model.parameters()).device

        self._info = ModelInfo(
            base_model_name=base_model_name,
            adapter_path=str(adapter_path),
            device=str(self._device),
        )

    @property
    def info(self) -> ModelInfo:
        return self._info

    def generate(
        self,
        user_prompt: str,
        max_new_tokens: int | None = None,
        temperature: float | None = None,
    ) -> tuple[str, int]:
        messages: list[dict[str, str]] = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        try:
            prompt_text = self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        except Exception as exc:
            raise RuntimeError(f"Ошибка построения chat-шаблона: {exc}") from exc

        inputs = self._tokenizer(prompt_text, return_tensors="pt")
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        mnt = max_new_tokens if max_new_tokens is not None else self._default_gen_cfg.max_new_tokens
        temp = self._default_gen_cfg.temperature if temperature is None else float(temperature)
        gen_kwargs = {
            "max_new_tokens": mnt,
            "temperature": temp,
            "top_p": self._default_gen_cfg.top_p,
            "do_sample": self._default_gen_cfg.do_sample,
        }

        try:
            with torch.no_grad():
                out = self._model.generate(**inputs, **gen_kwargs)
        except Exception as exc:
            raise RuntimeError(f"Ошибка генерации модели: {exc}") from exc

        input_len = inputs["input_ids"].shape[1]
        gen_tokens = out[0][input_len:]
        text = self._tokenizer.decode(gen_tokens, skip_special_tokens=True).strip()
        n_new = int(gen_tokens.shape[0])
        return text, n_new


def load_generator_from_env() -> TextGenerator:
    """Читает переменные окружения и создаёт генератор (вызывать один раз при старте)."""
    adapter_path = _resolve_adapter_path()
    if not _adapter_dir_looks_valid(adapter_path):
        raise FileNotFoundError(
            f"Не найден корректный адаптер в {adapter_path}. "
            "Загрузите веса в MODEL_PATH или задайте HF_WEIGHTS_REPO и HF_TOKEN."
        )

    gen_cfg = GenerationConfig(
        max_new_tokens=int(os.getenv("MAX_NEW_TOKENS", "256")),
        temperature=config.TEMPERATURE,
        top_p=config.TOP_P,
        do_sample=config.DO_SAMPLE,
    )

    return TextGenerator(
        base_model_name=config.BASE_MODEL_NAME,
        base_revision=config.BASE_MODEL_REVISION,
        adapter_path=adapter_path,
        system_prompt=config.SYSTEM_PROMPT,
        gen_cfg=gen_cfg,
    )
