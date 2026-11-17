"""Pydantic-модели входных данных, ответа LLM и итоговой карточки."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    manufacturer: str | None = None
    specs: dict[str, Any] = Field(default_factory=dict)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("название товара не должно быть пустым")
        return value

    @field_validator("specs")
    @classmethod
    def validate_specs(cls, value: dict[str, Any]) -> dict[str, Any]:
        for key, item in value.items():
            if not str(key).strip():
                raise ValueError("название характеристики не должно быть пустым")
            if isinstance(item, (dict, list)):
                raise ValueError(f"характеристика «{key}» должна быть строкой, числом или null")
        return value

    def characteristics(self) -> list[Characteristic]:
        result = [
            Characteristic(
                name=str(key).strip(),
                value="данных нет" if item is None or not str(item).strip() else str(item).strip(),
            )
            for key, item in self.specs.items()
        ]
        if not result:
            result.append(Characteristic(name="Технические характеристики", value="данных нет"))
        return result

    def missing_data(self) -> list[str]:
        missing: list[str] = []
        if not self.manufacturer or not self.manufacturer.strip():
            missing.append("manufacturer: данных нет — уточните производителя")
        if not self.specs:
            missing.append("specs: данных нет — добавьте технические характеристики")
        else:
            empty = [str(key) for key, value in self.specs.items() if _is_empty(value)]
            if empty:
                missing.append("specs: данных нет для полей — " + ", ".join(sorted(empty)))
        if not self.description or not self.description.strip():
            missing.append("description: данных нет — добавьте описание или фрагмент паспорта")
        return missing


class GeneratedContent(BaseModel):
    """Только те поля, которые разрешено генерировать модели."""

    model_config = ConfigDict(extra="forbid")

    seo_title: str
    seo_description: str
    search_queries: list[str]
    commercial_block: str


class Characteristic(BaseModel):
    name: str
    value: str


class ProductCard(BaseModel):
    seo_title: str
    seo_description: str
    characteristics: list[Characteristic]
    search_queries: list[str]
    commercial_block: str
    missing_data: list[str]
    product_name: str
    manufacturer: str
    generation_model: str
    generation_mode: str = "llm_draft"


def _is_empty(value: Any) -> bool:
    return value is None or not str(value).strip()
