from __future__ import annotations

import json
from dataclasses import replace

import pytest
from conftest import valid_raw

from product_card.config import Settings
from product_card.errors import GenerationValidationError, InputDataError
from product_card.service import CardGenerator, parse_products


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.feedback = []

    def generate(self, product_json, validation_feedback=None):
        self.feedback.append(validation_feedback)
        return self.responses.pop(0)


def test_service_preserves_specs_and_assembles_card(product):
    llm = FakeLLM([valid_raw()])
    card = CardGenerator(llm, Settings()).generate(product)
    assert card.seo_title.startswith("Манометр")
    assert [item.model_dump() for item in card.characteristics] == [
        {"name": "диапазон измерений", "value": "0–1,6 МПа"},
        {"name": "класс точности", "value": "1,5"},
        {"name": "присоединение", "value": "G1/2"},
        {"name": "диаметр корпуса", "value": "100 мм"},
    ]
    assert card.missing_data == []


def test_empty_values_are_explicitly_marked(product):
    product = product.model_copy(
        update={
            "manufacturer": "",
            "description": None,
            "specs": {**product.specs, "питание": None},
        }
    )
    card = CardGenerator(FakeLLM([valid_raw()]), Settings()).generate(product)
    assert card.manufacturer == "данных нет"
    assert card.characteristics[-1].value == "данных нет"
    assert any("manufacturer" in item for item in card.missing_data)
    assert any("description" in item for item in card.missing_data)


def test_invalid_answer_is_regenerated_with_feedback(product):
    invalid = json.loads(valid_raw())
    invalid["seo_description"] = "Слишком коротко"
    llm = FakeLLM([json.dumps(invalid), valid_raw()])
    card = CardGenerator(llm, replace(Settings(), max_attempts=2)).generate(product)
    assert len(card.seo_description) >= 800
    assert len(llm.feedback) == 2
    assert "800–1200" in llm.feedback[1]


def test_generation_stops_after_configured_attempts(product):
    llm = FakeLLM(["не JSON"])
    generator = CardGenerator(llm, replace(Settings(), max_attempts=1))
    with pytest.raises(GenerationValidationError, match="за 1 попытки"):
        generator.generate(product)


def test_parse_single_product_and_batch(product):
    assert len(parse_products(product.model_dump_json())) == 1
    assert len(parse_products(f"[{product.model_dump_json()}, {product.model_dump_json()}]")) == 2


@pytest.mark.parametrize("payload", ["{", "[]", '"текст"'])
def test_invalid_input_is_rejected(payload):
    with pytest.raises(InputDataError):
        parse_products(payload)
