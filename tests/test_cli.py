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


def test_safe_mode_saves_card_without_calling_llm(tmp_path, monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("safe-режим не должен создавать LLM-клиент")

    monkeypatch.setattr("product_card.cli.QwenClient", fail_if_called)
    source = tmp_path / "product.json"
    source.write_text(
        json.dumps({"name": "Прибор", "specs": {"питание": "24 В"}}, ensure_ascii=False),
        encoding="utf-8",
    )

    assert main([str(source), "-o", str(tmp_path / "out")]) == 0
    result = json.loads((tmp_path / "out" / "product_01.json").read_text(encoding="utf-8"))
    assert result["generation_mode"] == "safe"
    assert result["characteristics"] == [{"name": "питание", "value": "24 В"}]


def test_llm_draft_failure_does_not_cancel_safe_result(tmp_path, monkeypatch, capsys):
    from product_card.errors import GenerationValidationError

    class BrokenQwen:
        def __init__(self, settings):
            pass

        def generate(self, product_json, validation_feedback=None):
            raise GenerationValidationError("API недоступен")

    monkeypatch.setattr("product_card.cli.QwenClient", BrokenQwen)
    source = tmp_path / "product.json"
    source.write_text(json.dumps({"name": "Прибор", "specs": {}}), encoding="utf-8")

    assert main([str(source), "-o", str(tmp_path / "out"), "--save-llm-draft"]) == 0
    assert (tmp_path / "out" / "product_01.json").exists()
    assert not (tmp_path / "out" / "product_01_llm_draft.json").exists()
    assert "безопасный результат готов" in capsys.readouterr().err


def test_save_llm_draft_is_rejected_in_llm_mode(tmp_path, capsys):
    source = tmp_path / "product.json"
    source.write_text(json.dumps({"name": "Прибор"}), encoding="utf-8")

    assert main([str(source), "--mode", "llm", "--save-llm-draft"]) == 2
    assert "только вместе с --mode safe" in capsys.readouterr().err
