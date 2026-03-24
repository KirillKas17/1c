"""
Redis Cache Manager для кэширования результатов обработки данных.

Функционал:
- Кэш маппингов файлов (hash по сигнатуре файла)
- Кэш рассчитанных метрик (TTL: 1 час)
- Кэш прогнозов (TTL: 24 часа)
- Инвалидация при изменении данных
- Hit rate мониторинг
"""

import json
import hashlib
import redis
from typing import Any, Optional, Dict, List
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """Управление Redis кэшем для ускорения обработки данных."""
    
    # TTL значения в секундах
    TTL_MAPPINGS = 3600  # 1 час
    TTL_METRICS = 3600   # 1 час
    TTL_FORECASTS = 86400  # 24 часа
    TTL_RAW_DATA = 1800  # 30 минут
    
    def __init__(self, host: str = 'localhost', port: int = 6379, db: int = 0):
        """Инициализация Redis подключения."""
        try:
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                db=db,
                decode_responses=True,
                socket_connect_timeout=5
            )
            self.redis_client.ping()
            self.enabled = True
            logger.info(f"Redis подключён: {host}:{port}")
        except redis.ConnectionError:
            self.enabled = False
            self.redis_client = None
            logger.warning("Redis недоступен, кэширование отключено")
        
        # Статистика
        self.hits = 0
        self.misses = 0
    
    def _generate_file_signature(self, file_path: str, columns: List[str]) -> str:
        """Генерация уникальной сигнатуры файла для кэширования маппингов."""
        # Создаём хэш из пути файла и имён колонок
        data = f"{file_path}:{','.join(sorted(columns))}"
        return hashlib.md5(data.encode()).hexdigest()
    
    def _get_key(self, prefix: str, identifier: str) -> str:
        """Генерация ключа кэша."""
        return f"1c_dashboard:{prefix}:{identifier}"
    
    def get_mapping(self, file_signature: str) -> Optional[Dict[str, str]]:
        """Получение сохранённого маппинга по сигнатуре файла."""
        if not self.enabled:
            return None
        
        try:
            key = self._get_key("mapping", file_signature)
            cached = self.redis_client.get(key)
            
            if cached:
                self.hits += 1
                logger.debug(f"Cache HIT для маппинга: {file_signature}")
                return json.loads(cached)
            else:
                self.misses += 1
                logger.debug(f"Cache MISS для маппинга: {file_signature}")
                return None
        except Exception as e:
            logger.error(f"Ошибка получения маппинга из кэша: {e}")
            return None
    
    def set_mapping(self, file_signature: str, mapping: Dict[str, str], ttl: int = None) -> bool:
        """Сохранение маппинга в кэш."""
        if not self.enabled:
            return False
        
        try:
            key = self._get_key("mapping", file_signature)
            ttl = ttl or self.TTL_MAPPINGS
            self.redis_client.setex(key, ttl, json.dumps(mapping))
            logger.debug(f"Маппинг сохранён в кэш: {file_signature}")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения маппинга в кэш: {e}")
            return False
    
    def get_metrics(self, calculation_id: str) -> Optional[Dict[str, Any]]:
        """Получение рассчитанных метрик из кэша."""
        if not self.enabled:
            return None
        
        try:
            key = self._get_key("metrics", calculation_id)
            cached = self.redis_client.get(key)
            
            if cached:
                self.hits += 1
                logger.debug(f"Cache HIT для метрик: {calculation_id}")
                return json.loads(cached)
            else:
                self.misses += 1
                return None
        except Exception as e:
            logger.error(f"Ошибка получения метрик из кэша: {e}")
            return None
    
    def set_metrics(self, calculation_id: str, metrics: Dict[str, Any], ttl: int = None) -> bool:
        """Сохранение рассчитанных метрик в кэш."""
        if not self.enabled:
            return False
        
        try:
            key = self._get_key("metrics", calculation_id)
            ttl = ttl or self.TTL_METRICS
            self.redis_client.setex(key, ttl, json.dumps(metrics, default=str))
            logger.debug(f"Метрики сохранены в кэш: {calculation_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения метрик в кэш: {e}")
            return False
    
    def get_forecast(self, forecast_id: str) -> Optional[Dict[str, Any]]:
        """Получение прогноза из кэша."""
        if not self.enabled:
            return None
        
        try:
            key = self._get_key("forecast", forecast_id)
            cached = self.redis_client.get(key)
            
            if cached:
                self.hits += 1
                logger.debug(f"Cache HIT для прогноза: {forecast_id}")
                return json.loads(cached)
            else:
                self.misses += 1
                return None
        except Exception as e:
            logger.error(f"Ошибка получения прогноза из кэша: {e}")
            return None
    
    def set_forecast(self, forecast_id: str, forecast_data: Dict[str, Any], ttl: int = None) -> bool:
        """Сохранение прогноза в кэш."""
        if not self.enabled:
            return False
        
        try:
            key = self._get_key("forecast", forecast_id)
            ttl = ttl or self.TTL_FORECASTS
            self.redis_client.setex(key, ttl, json.dumps(forecast_data, default=str))
            logger.debug(f"Прогноз сохранён в кэш: {forecast_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения прогноза в кэш: {e}")
            return False
    
    def invalidate_pattern(self, pattern: str) -> int:
        """Инвалидация кэша по паттерну."""
        if not self.enabled:
            return 0
        
        try:
            keys = self.redis_client.keys(f"1c_dashboard:{pattern}*")
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"Инвалидировано {deleted} ключей по паттерну: {pattern}")
                return deleted
            return 0
        except Exception as e:
            logger.error(f"Ошибка инвалидации кэша: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики кэша."""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_percent": round(hit_rate, 2),
            "enabled": self.enabled
        }
    
    def clear_all(self) -> bool:
        """Очистка всего кэша (для тестов)."""
        if not self.enabled:
            return False
        
        try:
            keys = self.redis_client.keys("1c_dashboard:*")
            if keys:
                self.redis_client.delete(*keys)
            self.hits = 0
            self.misses = 0
            logger.info("Кэш полностью очищен")
            return True
        except Exception as e:
            logger.error(f"Ошибка очистки кэша: {e}")
            return False
    
    def health_check(self) -> bool:
        """Проверка здоровья Redis соединения."""
        if not self.enabled:
            return False
        
        try:
            self.redis_client.ping()
            return True
        except:
            return False


# Singleton instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Получение singleton экземпляра CacheManager."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager
