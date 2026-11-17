"""Настройки подключения к OpenAI-совместимому API локальной модели."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from .errors import InputDataError


@dataclass(frozen=True)
class Settings:
    base_url: str = "http://localhost:11434/v1"
    model: str = "qwen2.5:7b"
    api_key: str = "ollama"
    timeout: float = 120.0
    max_attempts: int = 4

    @classmethod
    def from_env(
        cls,
        *,
        base_url: str | None = None,
        model: str | None = None,
    ) -> Settings:
        load_dotenv()
        settings = cls(
            base_url=(base_url or os.getenv("LLM_BASE_URL") or cls.base_url).rstrip("/"),
            model=model or os.getenv("LLM_MODEL") or cls.model,
            api_key=os.getenv("LLM_API_KEY") or cls.api_key,
            timeout=_read_float("LLM_TIMEOUT", cls.timeout),
            max_attempts=_read_int("LLM_MAX_ATTEMPTS", cls.max_attempts),
        )
        if settings.timeout <= 0:
            raise InputDataError("LLM_TIMEOUT должен быть больше нуля.")
        if not 1 <= settings.max_attempts <= 5:
            raise InputDataError("LLM_MAX_ATTEMPTS должен быть от 1 до 5.")
        return settings


def _read_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise InputDataError(f"{name} должен быть числом.") from exc


def _read_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise InputDataError(f"{name} должен быть целым числом.") from exc
