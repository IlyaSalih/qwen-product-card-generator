from __future__ import annotations

import json

import pytest
from conftest import valid_raw

from product_card.errors import GenerationValidationError
from product_card.validation import parse_generated_content, validate_generated_content


def test_valid_content_has_no_errors(product):
    content = parse_generated_content(valid_raw())
    assert validate_generated_content(content, product) == []


def test_limits_and_duplicate_queries_are_checked(product):
    payload = json.loads(valid_raw())
    payload["seo_title"] = "З" * 71
    payload["seo_description"] = "Коротко"
    payload["search_queries"] = ["один", "один"]
    content = parse_generated_content(json.dumps(payload, ensure_ascii=False))
    errors = validate_generated_content(content, product)
    assert any("71 символов" in error for error in errors)
    assert any("800–1200" in error for error in errors)
    assert any("нужно 3–5" in error for error in errors)
    assert any("повторяются" in error for error in errors)


def test_unknown_numeric_value_is_rejected(product):
    payload = json.loads(valid_raw())
    payload["seo_description"] += " Дополнительное значение: 10 МПа."
    content = parse_generated_content(json.dumps(payload, ensure_ascii=False))
    errors = validate_generated_content(content, product)
    assert any("Необоснованные числовые значения" in error for error in errors)
    assert any("10" in error for error in errors)


def test_source_number_with_leading_zero_is_normalized(product):
    payload = json.loads(valid_raw())
    payload["seo_title"] = "Манометр DM 2"
    content = parse_generated_content(json.dumps(payload, ensure_ascii=False))
    assert validate_generated_content(content, product) == []


def test_json_inside_markdown_fence_is_accepted(product):
    content = parse_generated_content(f"```json\n{valid_raw()}\n```")
    assert validate_generated_content(content, product) == []


def test_invalid_model_json_has_readable_error():
    with pytest.raises(GenerationValidationError, match="некорректный JSON"):
        parse_generated_content("не JSON")
