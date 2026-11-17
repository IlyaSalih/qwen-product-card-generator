"""Предметные исключения приложения."""


class ProductCardError(Exception):
    """Базовая ошибка, которую можно показать пользователю без traceback."""


class InputDataError(ProductCardError):
    """Некорректный JSON или неподходящая структура входных данных."""


class LLMServiceError(ProductCardError):
    """Ошибка соединения с LLM или ответа сервера модели."""


class GenerationValidationError(ProductCardError):
    """Ответ модели не прошёл структурную или фактическую проверку."""
