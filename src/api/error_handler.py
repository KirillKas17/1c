"""
Глобальный обработчик ошибок для FastAPI и Streamlit.
Перехватывает кастомные исключения и возвращает понятные сообщения пользователю.
"""
from typing import Optional, Dict, Any
import streamlit as st
from src.core.exceptions import (
    DashboardBaseError,
    FileValidationError,
    StructureMismatchError,
    MappingError,
    CalculationError,
    ExternalServiceError,
    ForecastingError
)
from src.utils.logger import log_error, log_warning, set_request_context

class GlobalErrorHandler:
    """Централизованный обработчик ошибок."""
    
    @staticmethod
    def handle_exception(error: Exception, context: Optional[Dict[str, Any]] = None):
        """
        Обрабатывает исключение: логирует и возвращает безопасное сообщение.
        
        Args:
            error: Пойманное исключение
            context: Дополнительный контекст (user_id, request_id, filename)
            
        Returns:
            Dict с сообщением для пользователя
        """
        # Устанавливаем контекст для логирования
        if context:
            set_request_context(
                request_id=context.get("request_id", "unknown"),
                user_id=context.get("user_id", "anonymous")
            )
        
        # Логирование в зависимости от типа ошибки
        if isinstance(error, DashboardBaseError):
            log_warning(f"{error.error_code}: {str(error)}", context={"hint": error.hint, **(context or {})})
            return {
                "success": False,
                "error_code": error.error_code,
                "message": error.message,
                "hint": error.hint,
                "is_user_friendly": True
            }
        elif isinstance(error, (FileNotFoundError, IOError)):
            log_error(error, context=context)
            return {
                "success": False,
                "error_code": "FILE_NOT_FOUND",
                "message": "Файл не найден или недоступен.",
                "hint": "Проверьте путь к файлу и права доступа.",
                "is_user_friendly": True
            }
        elif isinstance(error, (KeyError, IndexError, ValueError)):
            log_error(error, context=context)
            return {
                "success": False,
                "error_code": "DATA_PROCESSING_ERROR",
                "message": "Ошибка при обработке данных.",
                "hint": "Возможно, файл содержит некорректные данные. Проверьте выгрузку из 1С.",
                "is_user_friendly": True
            }
        else:
            # Неожиданная ошибка - логируем стектрейс и показываем общее сообщение
            log_error(error, context=context)
            return {
                "success": False,
                "error_code": "INTERNAL_SERVER_ERROR",
                "message": "Произошла непредвиденная ошибка.",
                "hint": "Мы уже работаем над проблемой. Попробуйте повторить запрос позже или обратитесь в поддержку.",
                "is_user_friendly": True
            }
    
    @staticmethod
    def show_streamlit_error(error: Exception, context: Optional[Dict[str, Any]] = None):
        """Отображает ошибку в интерфейсе Streamlit."""
        result = GlobalErrorHandler.handle_exception(error, context)
        
        with st.container():
            st.error(f"**{result['message']}**")
            if result.get('hint'):
                st.info(f"💡 {result['hint']}")
            
            # Кнопка помощи для критических ошибок
            if result['error_code'] in ["STRUCTURE_MISMATCH", "FILE_VALIDATION_ERROR"]:
                if st.button("📥 Скачать пример правильного файла", key="download_sample"):
                    # Здесь должна быть логика скачивания sample-файла
                    st.write("*(Пример файла будет загружен)*")
                    
    @staticmethod
    def raise_if_error(result: Dict[str, Any]):
        """Если результат содержит ошибку, выбрасывает исключение."""
        if not result.get("success", True):
            error_code = result.get("error_code", "UNKNOWN_ERROR")
            message = result.get("message", "Неизвестная ошибка")
            hint = result.get("hint", "")
            
            # Маппинг кодов ошибок на классы исключений
            error_map = {
                "FILE_VALIDATION_ERROR": FileValidationError(message, hint),
                "STRUCTURE_MISMATCH": StructureMismatchError([], message, hint),
                "MAPPING_FAILED": MappingError(message, hint),
                "CALCULATION_ERROR": CalculationError("", message, hint),
                "EXTERNAL_SERVICE_ERROR": ExternalServiceError("", message),
                "FORECASTING_ERROR": ForecastingError(message, hint),
            }
            
            raise error_map.get(error_code, DashboardBaseError(message, error_code, hint))

# Удобные функции-обертки
def handle_error(error: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return GlobalErrorHandler.handle_exception(error, context)

def show_error(error: Exception, context: Optional[Dict[str, Any]] = None):
    GlobalErrorHandler.show_streamlit_error(error, context)
