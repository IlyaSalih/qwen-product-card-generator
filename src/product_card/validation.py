"""Разбор ответа модели и независимые проверки результата."""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation

from pydantic import ValidationError

from .errors import GenerationValidationError
from .models import GeneratedContent, ProductInput

_NUMBER_RE = re.compile(r"(?<![\w])[-+]?\d+(?:[.,]\d+)?", re.UNICODE)


def parse_generated_content(raw: str) -> GeneratedContent:
    """Принимает чистый JSON и распространённый вариант в Markdown-блоке."""
    candidate = raw.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\s*```$", "", candidate)
    if not candidate.startswith("{"):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start : end + 1]
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise GenerationValidationError(
            f"Модель вернула некорректный JSON (строка {exc.lineno}, столбец {exc.colno})."
        ) from exc
    try:
        return GeneratedContent.model_validate(payload)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(map(str, error['loc']))}: {error['msg']}" for error in exc.errors()
        )
        raise GenerationValidationError(f"Неожиданная структура ответа: {details}") from exc


def validate_generated_content(
    content: GeneratedContent,
    product: ProductInput,
) -> list[str]:
    errors: list[str] = []
    title = content.seo_title.strip()
    description = content.seo_description.strip()
    commercial = content.commercial_block.strip()
    queries = [query.strip() for query in content.search_queries]

    if not title:
        errors.append("seo_title: пустой заголовок")
    elif len(title) > 70:
        errors.append(f"seo_title: {len(title)} символов, нужно не более 70")
    if not 800 <= len(description) <= 1200:
        errors.append(f"seo_description: {len(description)} символов, нужно 800–1200")
    if not 3 <= len(queries) <= 5:
        errors.append(f"search_queries: получено {len(queries)}, нужно 3–5")
    if any(not query for query in queries):
        errors.append("search_queries: есть пустой запрос")
    normalized_queries = [query.casefold() for query in queries]
    if len(set(normalized_queries)) != len(normalized_queries):
        errors.append("search_queries: запросы повторяются")
    if not commercial:
        errors.append("commercial_block: пустой текст")

    source_numbers = extract_numbers(product.model_dump_json())
    generated_text = "\n".join([title, description, *queries, commercial])
    unknown_numbers = sorted(extract_numbers(generated_text) - source_numbers)
    if unknown_numbers:
        errors.append("Необоснованные числовые значения: " + ", ".join(unknown_numbers))
    return errors


def extract_numbers(text: str) -> set[str]:
    numbers: set[str] = set()
    for match in _NUMBER_RE.finditer(text):
        normalized = _normalize_number(match.group())
        if normalized is not None:
            numbers.add(normalized)
    return numbers


def _normalize_number(value: str) -> str | None:
    try:
        number = Decimal(value.replace(",", "."))
    except InvalidOperation:
        return None
    if number == 0:
        return "0"
    normalized = format(number.normalize(), "f")
    return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized
