"""
Модуль кастомных исключений для обработки ошибок бизнес-логики.
Каждое исключение содержит код ошибки, сообщение для пользователя и подсказку.
"""

class DashboardBaseError(Exception):
    """Базовое исключение для всех ошибок дашборда."""
    def __init__(self, message: str, error_code: str = "UNKNOWN_ERROR", hint: str = ""):
        self.message = message
        self.error_code = error_code
        self.hint = hint
        super().__init__(self.message)

    def to_dict(self):
        return {
            "error_code": self.error_code,
            "message": self.message,
            "hint": self.hint
        }

class FileValidationError(DashboardBaseError):
    """Ошибки валидации файла (формат, размер, повреждение)."""
    def __init__(self, message: str, hint: str = ""):
        super().__init__(message, error_code="FILE_VALIDATION_ERROR", hint=hint)

class StructureMismatchError(DashboardBaseError):
    """Структура файла не соответствует ожидаемой выгрузке 1С."""
    def __init__(self, missing_columns: list, message: str = "", hint: str = ""):
        default_msg = f"Не найдены обязательные колонки: {', '.join(missing_columns)}"
        default_hint = "Убедитесь, что вы выгрузили отчет 'Валовая прибыль' или 'Продажи' из 1С."
        super().__init__(
            message=message or default_msg,
            error_code="STRUCTURE_MISMATCH",
            hint=hint or default_hint
        )
        self.missing_columns = missing_columns

class MappingError(DashboardBaseError):
    """Ошибки при сопоставлении колонок (AI не смог распознать)."""
    def __init__(self, message: str = "Не удалось автоматически определить структуру данных.", hint: str = ""):
        default_hint = "Попробуйте вручную указать колонки в следующем шаге или проверьте файл на наличие пустых строк."
        super().__init__(message, error_code="MAPPING_FAILED", hint=hint or default_hint)

class CalculationError(DashboardBaseError):
    """Ошибки при расчете метрик (деление на ноль, неверные типы)."""
    def __init__(self, metric_name: str, message: str = "", hint: str = ""):
        default_msg = f"Ошибка при расчете метрики '{metric_name}'."
        super().__init__(message or default_msg, error_code="CALCULATION_ERROR", hint=hint)

class ExternalServiceError(DashboardBaseError):
    """Ошибки внешних сервисов (Redis, DB, LLM)."""
    def __init__(self, service_name: str, message: str = ""):
        msg = message or f"Сервис {service_name} временно недоступен."
        hint = "Попробуйте повторить запрос через минуту. Если проблема сохраняется, обратитесь в поддержку."
        super().__init__(msg, error_code="EXTERNAL_SERVICE_ERROR", hint=hint)

class ForecastingError(DashboardBaseError):
    """Ошибки при построении прогноза."""
    def __init__(self, message: str = "", hint: str = ""):
        default_msg = "Недостаточно данных для построения прогноза (требуется минимум 30 точек)."
        super().__init__(message or default_msg, error_code="FORECASTING_ERROR", hint=hint)
