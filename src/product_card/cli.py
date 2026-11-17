"""Точка входа командной строки."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import Settings
from .errors import InputDataError, ProductCardError
from .llm import QwenClient
from .render import render_markdown, save_card
from .safe import SafeCardGenerator
from .service import CardGenerator, parse_products


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="product-card",
        description=(
            "Генерация B2B-карточек: безопасный детерминированный результат "
            "и отдельный черновик локального Qwen."
        ),
    )
    parser.add_argument("input", type=Path, help="JSON-файл: один товар или массив товаров")
    parser.add_argument(
        "-o", "--output-dir", type=Path, default=Path("outputs"), help="Каталог результатов"
    )
    parser.add_argument("--base-url", help="Переопределить LLM_BASE_URL")
    parser.add_argument("--model", help="Переопределить LLM_MODEL")
    parser.add_argument(
        "--mode",
        choices=("safe", "llm"),
        help="safe — только входные факты (по умолчанию); llm — свободный черновик Qwen",
    )
    parser.add_argument(
        "--save-llm-draft",
        action="store_true",
        help=(
            "В safe-режиме дополнительно вызвать Qwen и сохранить черновик "
            "отдельными файлами; ошибка Qwen не отменяет безопасный результат"
        ),
    )
    parser.add_argument(
        "--validate-only", action="store_true", help="Проверить входной JSON без обращения к Qwen"
    )
    parser.add_argument("--print", action="store_true", help="Также вывести Markdown в терминал")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        text = args.input.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        print(f"Ошибка: файл не найден: {args.input}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Ошибка чтения {args.input}: {exc}", file=sys.stderr)
        return 2

    try:
        products = parse_products(text)
        settings = Settings.from_env(base_url=args.base_url, model=args.model, mode=args.mode)
        if args.save_llm_draft and settings.mode != "safe":
            raise InputDataError("--save-llm-draft используется только вместе с --mode safe.")
    except ProductCardError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2

    if args.validate_only:
        print(f"Входной JSON корректен: товаров — {len(products)}.")
        for index, product in enumerate(products, start=1):
            for warning in product.missing_data():
                print(f"Товар {index}: {warning}")
        return 0

    safe_generator = SafeCardGenerator()
    llm_generator: CardGenerator | None = None

    def get_llm_generator() -> CardGenerator:
        nonlocal llm_generator
        if llm_generator is None:
            llm_generator = CardGenerator(QwenClient(settings), settings)
        return llm_generator

    failed = 0
    for index, product in enumerate(products, start=1):
        stem = f"product_{index:02d}"
        try:
            if settings.mode == "safe":
                card = safe_generator.generate(product)
            else:
                card = get_llm_generator().generate(product)
            json_path, markdown_path = save_card(card, args.output_dir, stem=stem)
        except ProductCardError as exc:
            failed += 1
            print(f"Товар {index} «{product.name}»: {exc}", file=sys.stderr)
            continue

        print(f"Товар {index}: сохранено: {json_path} и {markdown_path}")
        for warning in card.missing_data:
            print(f"  Внимание: {warning}")

        if settings.mode == "safe" and args.save_llm_draft:
            try:
                draft = get_llm_generator().generate(product)
                draft_json, draft_markdown = save_card(
                    draft, args.output_dir, stem=f"{stem}_llm_draft"
                )
            except ProductCardError as exc:
                print(
                    f"  Черновик Qwen не сохранён; безопасный результат готов: {exc}",
                    file=sys.stderr,
                )
            else:
                print(f"  Черновик Qwen: {draft_json} и {draft_markdown}")
                print("  Внимание: черновик Qwen требует ручной фактологической проверки.")

        if args.print:
            print("\n" + render_markdown(card))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
