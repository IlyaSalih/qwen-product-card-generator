"""Детерминированная сборка карточки только из подтверждённых входных данных."""

from __future__ import annotations

import re

from .models import Characteristic, ProductCard, ProductInput

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_UNSAFE_INSTRUCTION = re.compile(
    r"\b(?:игнорир\w*|забудь|напиши|выведи|выполни|добавь\w*|сгенериру\w*|"
    r"покупай|prompt|system)\b"
    r"|системн\w*\s+правил"
    r"|инструкци\w*\s+модел",
    re.IGNORECASE,
)
_APPLICATION = re.compile(
    r"\b(?:предназнач\w*|применя\w*|использу\w*|област\w*\s+применения)\b",
    re.IGNORECASE,
)
_GUIDANCE = (
    (
        "При подборе необходимо сопоставить подтверждённые характеристики "
        "с требованиями конкретной задачи. Сведения, которых нет во входных данных, "
        "не следует заменять предположениями: их нужно запросить у производителя "
        "или поставщика. Это особенно важно для назначения, условий эксплуатации "
        "и совместимости прибора."
    ),
    (
        "Перед публикацией карточки контент-менеджеру следует сверить описание "
        "с технической документацией и проверить, что коммерческий блок не расширяет "
        "подтверждённую область применения. Сокращения, коды и обозначения не "
        "раскрываются без исходного описания. После получения недостающих данных "
        "текст можно дополнить без изменения уже подтверждённых значений."
    ),
    (
        "Если исходные сведения ограничены, результат используется как список фактов "
        "и вопросов для уточнения, а не как готовое обоснование выбора. Ответственный "
        "специалист должен подтвердить пригодность конкретной модификации перед заказом."
    ),
)


class SafeCardGenerator:
    """Создаёт безопасный результат без обращения к LLM."""

    def generate(self, product: ProductInput) -> ProductCard:
        manufacturer = (
            product.manufacturer.strip()
            if product.manufacturer and product.manufacturer.strip()
            else "данных нет"
        )
        source_sentences, rejected = _safe_source_sentences(product.description)
        missing = product.missing_data()
        if rejected:
            missing.append(
                "description: часть текста отклонена фильтром безопасности; "
                "проверьте исходное описание"
            )

        summary = _characteristics_summary(product.characteristics())
        identity = f"{_clip(product.name, 180)}. Производитель: {_clip(manufacturer, 120)}."
        source_text = _join_limited(source_sentences, 480)
        if not source_text:
            source_text = "Описание товара: данных нет."
        parts = [identity, source_text, summary]
        if missing:
            parts.append("Требуют уточнения: " + "; ".join(missing) + ".")
        description = _fit_description(parts)

        return ProductCard(
            seo_title=_make_title(product.name, manufacturer),
            seo_description=description,
            characteristics=product.characteristics(),
            search_queries=_make_queries(product, manufacturer),
            commercial_block=_make_commercial_block(source_sentences),
            missing_data=missing,
            product_name=product.name,
            manufacturer=manufacturer,
            generation_model="deterministic-safe-renderer",
            generation_mode="safe",
        )


def _safe_source_sentences(text: str | None) -> tuple[list[str], bool]:
    if not text or not text.strip():
        return [], False
    normalized = " ".join(text.split())
    sentences = [part.strip() for part in _SENTENCE_SPLIT.split(normalized) if part.strip()]
    safe = [
        sentence
        for sentence in sentences
        if len(sentence) >= 25 and not _UNSAFE_INSTRUCTION.search(sentence)
    ]
    return safe, len(safe) != len(sentences)


def _characteristics_summary(characteristics: list[Characteristic], limit: int = 620) -> str:
    confirmed = [item for item in characteristics if item.value != "данных нет"]
    if not confirmed:
        return "Технические характеристики: данных нет."
    selected: list[str] = []
    size = 0
    for item in confirmed:
        phrase = f"{item.name}: {item.value}"
        if selected and size + len(phrase) + 2 > limit:
            break
        if len(phrase) > limit:
            break
        selected.append(phrase)
        size += len(phrase) + 2
    if not selected:
        return "Подтверждённые характеристики приведены в структурированном списке ниже."
    suffix = ""
    if len(selected) < len(confirmed):
        suffix = " Полный перечень приведён в структурированном списке ниже."
    return "Подтверждённые характеристики: " + "; ".join(selected) + "." + suffix


def _fit_description(parts: list[str]) -> str:
    description = " ".join(part.strip() for part in parts if part.strip())
    if len(description) > 1150:
        description = " ".join((parts[0], parts[2]))
    guidance_sentences = [
        sentence
        for paragraph in _GUIDANCE
        for sentence in _SENTENCE_SPLIT.split(paragraph)
        if sentence
    ]
    for sentence in guidance_sentences:
        if len(description) >= 900:
            break
        if len(description) + len(sentence) + 1 <= 1150:
            description += " " + sentence
    if len(description) > 1200:
        description = _clip(description, 1200)
    return description


def _make_title(name: str, manufacturer: str) -> str:
    title = name.strip()
    if manufacturer != "данных нет" and manufacturer.casefold() not in name.casefold():
        title += f" — {manufacturer}"
    return _clip(title, 70)


def _make_queries(product: ProductInput, manufacturer: str) -> list[str]:
    name = product.name.strip()
    candidates = [name]
    if manufacturer != "данных нет":
        candidates.append(f"{manufacturer} {name}")
    candidates.extend((f"{name} характеристики", f"{name} описание"))
    first_value = next(
        (
            item.value
            for item in product.characteristics()
            if item.value != "данных нет" and item.name != "Технические характеристики"
        ),
        None,
    )
    if first_value:
        candidates.append(f"{name} {first_value}")
    candidates.append(f"{name} технические данные")

    result: list[str] = []
    seen: set[str] = set()
    for query in candidates:
        normalized = " ".join(query.split())
        key = normalized.casefold()
        if key not in seen:
            result.append(normalized)
            seen.add(key)
        if len(result) == 5:
            break
    return result


def _make_commercial_block(source_sentences: list[str]) -> str:
    applications = [sentence for sentence in source_sentences if _APPLICATION.search(sentence)]
    application_text = _join_limited(applications, 420)
    if application_text:
        return (
            application_text + " При подготовке предложения менеджеру следует опираться только на "
            "перечисленные характеристики и уточнить отсутствующие условия подбора."
        )
    return (
        "Назначение и решаемые задачи: данных нет. Менеджеру необходимо запросить "
        "описание или фрагмент технического паспорта, а затем подтвердить область "
        "применения перед подготовкой предложения."
    )


def _join_limited(sentences: list[str], limit: int) -> str:
    result: list[str] = []
    size = 0
    for sentence in sentences:
        if result and size + len(sentence) + 1 > limit:
            break
        if len(sentence) > limit:
            break
        result.append(sentence)
        size += len(sentence) + 1
    return " ".join(result)


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    shortened = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,.;:—-")
    if len(shortened) < limit // 2:
        shortened = text[: limit - 1].rstrip()
    return shortened + "…"
