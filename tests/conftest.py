from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from product_card.models import ProductInput  # noqa: E402


@pytest.fixture
def product() -> ProductInput:
    return ProductInput.model_validate(
        {
            "name": "Манометр показывающий DM 02",
            "manufacturer": "Манотомь",
            "specs": {
                "диапазон измерений": "0–1,6 МПа",
                "класс точности": "1,5",
                "присоединение": "G1/2",
                "диаметр корпуса": "100 мм",
            },
            "description": "Прибор предназначен для измерения избыточного давления.",
        }
    )


def valid_raw() -> str:
    return json.dumps(
        {
            "seo_title": "Манометр показывающий DM 02 — Манотомь",
            "seo_description": (
                "Прибор предназначен для измерения избыточного давления. "
                "Описание содержит только сведения из исходных данных. "
            )
            * 9,
            "search_queries": [
                "манометр показывающий DM 02",
                "манометр Манотомь",
                "манометр 0–1,6 МПа",
            ],
            "commercial_block": (
                "Подходит пользователям, которым нужен прибор для измерения избыточного давления. "
                "Перед заказом следует сверить указанные характеристики с задачей."
            ),
        },
        ensure_ascii=False,
    )
