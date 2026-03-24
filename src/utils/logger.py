"""
Модуль структурированного логирования.
Форматирует логи в JSON, добавляет контекст (request_id, user_id) и маскирует чувствительные данные.
"""
import logging
import json
import sys
import traceback
from datetime import datetime
from typing import Any, Dict, Optional
import re

# Глобальный ID запроса (в реальном приложении генерируется на каждый запрос)
_current_request_id: str = ""
_current_user_id: str = ""

class JsonFormatter(logging.Formatter):
    """Форматтер для вывода логов в JSON."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": _current_request_id,
            "user_id": _current_user_id,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Добавляем стектрейс если есть ошибка
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else "Unknown",
                "message": str(record.exc_info[1]) if record.exc_info[1] else "",
                "traceback": traceback.format_exception(*record.exc_info)
            }
            
        # Добавляем дополнительные атрибуты если есть
        for key, value in record.__dict__.items():
            if key not in ['msg', 'args', 'levelname', 'levelno', 'pathname', 'filename', 
                           'module', 'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                           'thread', 'threadName', 'processName', 'process', 'exc_info', 'exc_text',
                           'message', 'asctime']:
                log_data[key] = self._sanitize_value(value)
                
        return json.dumps(log_data, ensure_ascii=False, default=str)
    
    def _sanitize_value(self, value: Any) -> Any:
        """Маскирует чувствительные данные в логах."""
        if isinstance(value, str):
            # Маскировка email
            value = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[EMAIL_MASKED]', value)
            # Маскировка токенов (простая эвристика)
            value = re.sub(r'(token|key|secret|password)[=:]\s*\S+', r'\1=[MASKED]', value, flags=re.IGNORECASE)
        return value

def setup_logger(name: str = "dashboard", level: int = logging.INFO) -> logging.Logger:
    """Настраивает и возвращает логгер с JSON форматированием."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Если хендлеры уже есть, не добавляем повторно
    if logger.handlers:
        return logger
        
    # Консольный хендлер (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(JsonFormatter())
    logger.addHandler(console_handler)
    
    return logger

def set_request_context(request_id: str, user_id: str = ""):
    """Устанавливает контекст текущего запроса для логирования."""
    global _current_request_id, _current_user_id
    _current_request_id = request_id
    _current_user_id = user_id

def clear_request_context():
    """Очищает контекст запроса."""
    global _current_request_id, _current_user_id
    _current_request_id = ""
    _current_user_id = ""

# Создаем дефолтный логгер
logger = setup_logger()

def log_error(error: Exception, context: Optional[Dict[str, Any]] = None):
    """Удобная функция для логирования ошибок с контекстом."""
    if context:
        logger.error(
            f"{error.__class__.__name__}: {str(error)}",
            exc_info=True
        )
        for k, v in context.items():
            logger.info(f"Context: {k}={v}")
    else:
        logger.error(
            f"{error.__class__.__name__}: {str(error)}",
            exc_info=True
        )

def log_info(message: str, context: Optional[Dict[str, Any]] = None):
    """Удобная функция для информационных логов."""
    logger.info(message)
    if context:
        for k, v in context.items():
            logger.info(f"Context: {k}={v}")

def log_warning(message: str, context: Optional[Dict[str, Any]] = None):
    """Удобная функция для предупреждений."""
    logger.warning(message)
    if context:
        for k, v in context.items():
            logger.info(f"Context: {k}={v}")
