"""Точка входа командной строки."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import Settings
from .errors import ProductCardError
from .llm import QwenClient
from .render import render_markdown, save_card
from .service import CardGenerator, parse_products


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="product-card",
        description="Генерация черновиков B2B-карточек через локальный Qwen.",
    )
    parser.add_argument("input", type=Path, help="JSON-файл: один товар или массив товаров")
    parser.add_argument(
        "-o", "--output-dir", type=Path, default=Path("outputs"), help="Каталог результатов"
    )
    parser.add_argument("--base-url", help="Переопределить LLM_BASE_URL")
    parser.add_argument("--model", help="Переопределить LLM_MODEL")
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
        settings = Settings.from_env(base_url=args.base_url, model=args.model)
    except ProductCardError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2

    if args.validate_only:
        print(f"Входной JSON корректен: товаров — {len(products)}.")
        for index, product in enumerate(products, start=1):
            for warning in product.missing_data():
                print(f"Товар {index}: {warning}")
        return 0

    generator = CardGenerator(QwenClient(settings), settings)
    failed = 0
    for index, product in enumerate(products, start=1):
        try:
            card = generator.generate(product)
            json_path, markdown_path = save_card(card, args.output_dir, stem=f"product_{index:02d}")
        except ProductCardError as exc:
            failed += 1
            print(f"Товар {index} «{product.name}»: {exc}", file=sys.stderr)
            continue
        print(f"Товар {index}: сохранено: {json_path} и {markdown_path}")
        for warning in card.missing_data:
            print(f"  Внимание: {warning}")
        if args.print:
            print("\n" + render_markdown(card))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
