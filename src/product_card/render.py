"""Представление результата в Markdown и сохранение обоих форматов."""

from __future__ import annotations

import json
from pathlib import Path

from .models import ProductCard


def render_markdown(card: ProductCard) -> str:
    characteristics = "\n".join(f"- **{item.name}:** {item.value}" for item in card.characteristics)
    queries = "\n".join(f"- {query}" for query in card.search_queries)
    missing = (
        "\n".join(f"- {item}" for item in card.missing_data)
        if card.missing_data
        else "Все основные входные поля заполнены."
    )
    return f"""# {card.seo_title}

## SEO-описание

{card.seo_description}

## Ключевые характеристики

{characteristics}

## Поисковые запросы

{queries}

## Commercial-блок для менеджера

{card.commercial_block}

## Данные, требующие уточнения

{missing}

---

- Исходный товар: {card.product_name}
- Производитель: {card.manufacturer}
- Модель генерации: `{card.generation_model}`
- Режим генерации: `{card.generation_mode}`
"""


def save_card(card: ProductCard, output_dir: Path, stem: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    json_path.write_text(
        json.dumps(card.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(card), encoding="utf-8")
    return json_path, markdown_path
