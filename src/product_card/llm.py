"""Минимальный адаптер Qwen через OpenAI-совместимый Chat Completions API."""

from __future__ import annotations

from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from .config import Settings
from .errors import LLMServiceError
from .prompts import SYSTEM_PROMPT, build_user_prompt


class QwenClient:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.settings = settings
        self._client = client or OpenAI(
            base_url=settings.base_url,
            api_key=settings.api_key,
            timeout=settings.timeout,
            max_retries=1,
        )

    def generate(self, product_json: str, validation_feedback: str | None = None) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self.settings.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": build_user_prompt(product_json, validation_feedback),
                    },
                ],
                temperature=0.0,
                max_tokens=2200,
            )
        except APITimeoutError as exc:
            raise LLMServiceError(
                f"Qwen не ответил за {self.settings.timeout:g} секунд. "
                "Проверьте загрузку модели или увеличьте LLM_TIMEOUT."
            ) from exc
        except APIConnectionError as exc:
            raise LLMServiceError(
                f"Не удалось подключиться к Qwen: {self.settings.base_url}. "
                "Запустите локальный сервер и проверьте LLM_BASE_URL."
            ) from exc
        except APIStatusError as exc:
            detail = _safe_api_detail(exc)
            raise LLMServiceError(
                f"Сервер Qwen вернул HTTP {exc.status_code}. "
                f"Проверьте имя модели и настройки API. {detail}"
            ) from exc
        except Exception as exc:
            raise LLMServiceError(f"Неожиданная ошибка обращения к Qwen: {exc}") from exc

        if not response.choices:
            raise LLMServiceError("Qwen вернул пустой список вариантов ответа.")
        content = response.choices[0].message.content
        if not content or not content.strip():
            raise LLMServiceError("Qwen вернул пустой текст ответа.")
        return content


def _safe_api_detail(exc: APIStatusError) -> str:
    """Не выводим заголовки и другие данные запроса, где может оказаться ключ."""
    if isinstance(exc.body, dict):
        error = exc.body.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])[:500]
        if error:
            return str(error)[:500]
    return ""
