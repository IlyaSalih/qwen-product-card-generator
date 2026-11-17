from __future__ import annotations

import json

from product_card.cli import main
from product_card.models import ProductCard
from product_card.render import render_markdown, save_card


def test_validate_only_does_not_call_llm(tmp_path, capsys):
    source = tmp_path / "product.json"
    source.write_text(
        json.dumps({"name": "Прибор", "specs": {}}, ensure_ascii=False), encoding="utf-8"
    )
    assert main([str(source), "--validate-only"]) == 0
    captured = capsys.readouterr()
    assert "Входной JSON корректен" in captured.out
    assert "данных нет" in captured.out


def test_invalid_json_returns_exit_code_2(tmp_path, capsys):
    source = tmp_path / "broken.json"
    source.write_text("{", encoding="utf-8")
    assert main([str(source)]) == 2
    assert "Некорректный входной JSON" in capsys.readouterr().err


def test_missing_file_returns_exit_code_2(tmp_path, capsys):
    assert main([str(tmp_path / "missing.json")]) == 2
    assert "файл не найден" in capsys.readouterr().err


def test_card_is_saved_as_json_and_markdown(tmp_path):
    card = ProductCard.model_validate(
        {
            "seo_title": "Заголовок",
            "seo_description": "Описание",
            "characteristics": [{"name": "Питание", "value": "данных нет"}],
            "search_queries": ["запрос"],
            "commercial_block": "Для менеджера",
            "missing_data": [],
            "product_name": "Прибор",
            "manufacturer": "данных нет",
            "generation_model": "test",
        }
    )
    json_path, markdown_path = save_card(card, tmp_path, "product_01")
    assert json.loads(json_path.read_text(encoding="utf-8"))["product_name"] == "Прибор"
    markdown = render_markdown(card)
    assert markdown_path.read_text(encoding="utf-8") == markdown
    assert "**Питание:** данных нет" in markdown
