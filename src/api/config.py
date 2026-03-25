"""
Конфигурация приложения через переменные окружения
"""
from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Настройки приложения из переменных окружения"""
    
    # === Application ===
    APP_NAME: str = "1C Dashboard Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development, staging, production
    
    # === Server ===
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    
    # === Security ===
    # Генерируем безопасный ключ по умолчанию (минимум 64 символа)
    SECRET_KEY: str = "your-secret-key-change-in-production-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # === Database ===
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/dashboard_db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    
    # === Redis (for caching & sessions) ===
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # === File Storage ===
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 100
    ALLOWED_EXTENSIONS: list = ["xlsx", "xls", "csv"]
    
    # === Payment (YooKassa) ===
    YOOKASSA_SHOP_ID: str = ""
    YOOKASSA_SECRET_KEY: str = ""
    YOOKASSA_RETURN_URL: str = "http://localhost:8000/payment/callback"
    PAYMENT_WEBHOOK_SECRET: str = ""
    
    # === Email (for notifications) ===
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "noreply@dashboard.service"
    FROM_NAME: str = "1C Dashboard"
    SUPPORT_EMAIL: str = "support@dashboard.service"
    FRONTEND_URL: str = "http://localhost:3000"
    
    # === Telegram Fallback ===
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_ADMIN_CHAT_ID: str = ""
    
    # === SSL/TLS ===
    SSL_CERT_FILE: str = "/app/certs/server.crt"
    SSL_KEY_FILE: str = "/app/certs/server.key"
    SSL_DOMAIN: str = "localhost"
    SSL_EMAIL: str = "admin@localhost"
    SSL_ENV: str = "dev"  # dev or prod
    
    # === AI/LLM ===
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "meta-llama/llama-3-70b-instruct"
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"
    LLM_CONFIDENCE_THRESHOLD_DICTIONARY: float = 0.9
    LLM_CONFIDENCE_THRESHOLD_HEURISTIC: float = 0.7
    LLM_CONFIDENCE_THRESHOLD_LLM: float = 0.6
    
    # === Monitoring ===
    SENTRY_DSN: Optional[str] = None
    PROMETHEUS_ENABLED: bool = False
    
    # === Rate Limiting ===
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # === CORS ===
    CORS_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:8080",
        "https://dashboard.local",
    ]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Кэшированный экземпляр настроек"""
    return Settings()


# Глобальный экземпляр для импорта
settings = get_settings()
