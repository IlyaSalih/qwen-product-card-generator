"""Сценарий генерации карточки и загрузка входных JSON-файлов."""

from __future__ import annotations

import json
from typing import Protocol

from pydantic import ValidationError

from .config import Settings
from .errors import GenerationValidationError, InputDataError
from .models import GeneratedContent, ProductCard, ProductInput
from .validation import parse_generated_content, validate_generated_content


class TextGenerator(Protocol):
    def generate(self, product_json: str, validation_feedback: str | None = None) -> str: ...


class CardGenerator:
    def __init__(self, llm: TextGenerator, settings: Settings) -> None:
        self.llm = llm
        self.settings = settings

    def generate(self, product: ProductInput) -> ProductCard:
        feedback: str | None = None
        last_errors: list[str] = []
        product_json = product.model_dump_json(exclude_none=False)

        for _attempt in range(1, self.settings.max_attempts + 1):
            raw = self.llm.generate(product_json, feedback)
            try:
                content = parse_generated_content(raw)
                last_errors = validate_generated_content(content, product)
            except GenerationValidationError as exc:
                content = None
                last_errors = [str(exc)]
            if content is not None and not last_errors:
                return _assemble_card(content, product, self.settings.model)
            feedback = "\n".join(f"- {error}" for error in last_errors)

        details = " ".join(last_errors)
        raise GenerationValidationError(
            f"Qwen не выдал корректный результат за {self.settings.max_attempts} попытки. {details}"
        )


def parse_products(text: str) -> list[ProductInput]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InputDataError(
            f"Некорректный входной JSON: строка {exc.lineno}, столбец {exc.colno}: {exc.msg}."
        ) from exc
    if isinstance(payload, dict):
        items = [payload]
    elif isinstance(payload, list) and payload:
        items = payload
    else:
        raise InputDataError(
            "Входной JSON должен быть объектом товара или непустым массивом объектов."
        )
    try:
        return [ProductInput.model_validate(item) for item in items]
    except ValidationError as exc:
        details = "; ".join(
            "товар "
            f"{error['loc'][0] + 1 if error['loc'] and isinstance(error['loc'][0], int) else '?'}, "
            f"{'.'.join(map(str, error['loc'][1:]))}: {error['msg']}"
            for error in exc.errors()
        )
        raise InputDataError(f"Ошибка во входных данных: {details}") from exc


def _assemble_card(
    content: GeneratedContent,
    product: ProductInput,
    model: str,
) -> ProductCard:
    return ProductCard(
        seo_title=content.seo_title.strip(),
        seo_description=content.seo_description.strip(),
        characteristics=product.characteristics(),
        search_queries=[query.strip() for query in content.search_queries],
        commercial_block=content.commercial_block.strip(),
        missing_data=product.missing_data(),
        product_name=product.name,
        manufacturer=(
            product.manufacturer.strip()
            if product.manufacturer and product.manufacturer.strip()
            else "данных нет"
        ),
        generation_model=model,
    )
