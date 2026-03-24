"""
Тесты для модулей Infrastructure & Scale Prep.

Проверяют:
- Redis Cache Manager
- JWT Authentication
- Mapping Learner
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
import sys
sys.path.insert(0, '/workspace/src')


# ==================== Cache Manager Tests ====================

class TestCacheManager:
    """Тесты для Redis Cache Manager."""
    
    def test_cache_manager_init_without_redis(self):
        """Инициализация без доступного Redis."""
        from src.core.cache_manager import CacheManager
        
        with patch('redis.Redis') as mock_redis:
            mock_redis.side_effect = Exception("Connection refused")
            cache = CacheManager()
            
            assert cache.enabled == False
            assert cache.redis_client is None
    
    def test_generate_file_signature(self):
        """Генерация сигнатуры файла."""
        from src.core.cache_manager import CacheManager
        
        cache = CacheManager.__new__(CacheManager)
        cache.enabled = False
        
        columns = ["Дата", "Сумма", "Контрагент"]
        sig1 = cache._generate_file_signature("file1.xlsx", columns)
        sig2 = cache._generate_file_signature("file1.xlsx", columns)
        sig3 = cache._generate_file_signature("file2.xlsx", columns)
        
        assert sig1 == sig2  # Одинаковые файлы
        assert sig1 != sig3  # Разные файлы
    
    def test_get_key_format(self):
        """Формат ключей кэша."""
        from src.core.cache_manager import CacheManager
        
        cache = CacheManager.__new__(CacheManager)
        key = cache._get_key("mapping", "abc123")
        
        assert key == "1c_dashboard:mapping:abc123"
    
    def test_set_get_mapping_disabled(self):
        """Работа с маппингами при отключенном кэше."""
        from src.core.cache_manager import CacheManager
        
        cache = CacheManager.__new__(CacheManager)
        cache.enabled = False
        
        result = cache.set_mapping("sig1", {"col1": "field1"})
        assert result == False
        
        retrieved = cache.get_mapping("sig1")
        assert retrieved is None
    
    def test_set_get_metrics_disabled(self):
        """Работа с метриками при отключенном кэше."""
        from src.core.cache_manager import CacheManager
        
        cache = CacheManager.__new__(CacheManager)
        cache.enabled = False
        
        metrics = {"revenue": 1000000, "cost": 700000}
        result = cache.set_metrics("calc1", metrics)
        assert result == False
        
        retrieved = cache.get_metrics("calc1")
        assert retrieved is None
    
    def test_set_get_forecast_disabled(self):
        """Работа с прогнозами при отключенном кэше."""
        from src.core.cache_manager import CacheManager
        
        cache = CacheManager.__new__(CacheManager)
        cache.enabled = False
        
        forecast = {"values": [1, 2, 3], "trend": "growing"}
        result = cache.set_forecast("fc1", forecast)
        assert result == False
        
        retrieved = cache.get_forecast("fc1")
        assert retrieved is None
    
    def test_get_stats_empty(self):
        """Статистика пустого кэша."""
        from src.core.cache_manager import CacheManager
        
        cache = CacheManager.__new__(CacheManager)
        cache.enabled = False
        cache.hits = 0
        cache.misses = 0
        
        stats = cache.get_stats()
        
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate_percent"] == 0
        assert stats["enabled"] == False
    
    def test_invalidate_pattern_disabled(self):
        """Инвалидация паттерна при отключенном кэше."""
        from src.core.cache_manager import CacheManager
        
        cache = CacheManager.__new__(CacheManager)
        cache.enabled = False
        
        result = cache.invalidate_pattern("mapping")
        assert result == 0


# ==================== JWT Auth Tests ====================

class TestJWTAuth:
    """Тесты для JWT Authentication."""
    
    def test_password_hashing(self):
        """Хэширование пароля."""
        from src.api.auth import JWTAuthManager
        
        auth = JWTAuthManager(secret_key="test_secret")
        password = "MySecurePassword123"
        
        hashed = auth.hash_password(password)
        
        assert hashed != password
        assert len(hashed) > 50
        assert auth.verify_password(password, hashed) == True
        assert auth.verify_password("wrong_password", hashed) == False
    
    def test_create_access_token(self):
        """Создание access токена."""
        from src.api.auth import JWTAuthManager
        
        auth = JWTAuthManager(secret_key="test_secret")
        token = auth.create_access_token("user123", "test@example.com", "user")
        
        assert isinstance(token, str)
        assert len(token) > 50
    
    def test_verify_access_token(self):
        """Верификация access токена."""
        from src.api.auth import JWTAuthManager
        
        auth = JWTAuthManager(secret_key="test_secret")
        token = auth.create_access_token("user123", "test@example.com", "admin")
        
        payload = auth.verify_token(token, token_type="access")
        
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["email"] == "test@example.com"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"
    
    def test_create_refresh_token(self):
        """Создание refresh токена."""
        from src.api.auth import JWTAuthManager
        
        auth = JWTAuthManager(secret_key="test_secret")
        token = auth.create_refresh_token("user123")
        
        assert isinstance(token, str)
        assert token in auth.token_store
    
    def test_verify_refresh_token(self):
        """Верификация refresh токена."""
        from src.api.auth import JWTAuthManager
        
        auth = JWTAuthManager(secret_key="test_secret")
        token = auth.create_refresh_token("user123")
        
        payload = auth.verify_token(token, token_type="refresh")
        
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["type"] == "refresh"
    
    def test_wrong_token_type(self):
        """Проверка неправильного типа токена."""
        from src.api.auth import JWTAuthManager
        
        auth = JWTAuthManager(secret_key="test_secret")
        access_token = auth.create_access_token("user123", "test@example.com")
        
        # Пытаемся верифицировать access токен как refresh
        payload = auth.verify_token(access_token, token_type="refresh")
        
        assert payload is None
    
    def test_blacklist_token(self):
        """Добавление токена в blacklist."""
        from src.api.auth import JWTAuthManager
        
        auth = JWTAuthManager(secret_key="test_secret")
        token = auth.create_access_token("user123", "test@example.com")
        
        # Токен валиден
        assert auth.verify_token(token) is not None
        
        # Добавляем в blacklist
        auth.blacklist_token(token)
        
        # Токен больше не валиден
        assert auth.verify_token(token) is None
    
    def test_logout(self):
        """Logout пользователя."""
        from src.api.auth import JWTAuthManager
        
        auth = JWTAuthManager(secret_key="test_secret")
        access = auth.create_access_token("user123", "test@example.com")
        refresh = auth.create_refresh_token("user123")
        
        # Logout
        auth.logout(access, refresh)
        
        # Оба токена невалидны
        assert auth.verify_token(access) is None
        assert auth.verify_token(refresh, token_type="refresh") is None
    
    def test_rate_limiting(self):
        """Rate limiting запросов."""
        from src.api.auth import JWTAuthManager
        
        auth = JWTAuthManager(secret_key="test_secret")
        auth.rate_limit = 5  # Уменьшаем для теста
        
        user_id = "test_user"
        
        # Первые 5 запросов разрешены
        for i in range(5):
            assert auth.check_rate_limit(user_id) == True
        
        # 6-й запрос заблокирован
        assert auth.check_rate_limit(user_id) == False
    
    def test_get_user_info(self):
        """Получение информации о пользователе."""
        from src.api.auth import JWTAuthManager
        
        auth = JWTAuthManager(secret_key="test_secret")
        token = auth.create_access_token("user123", "test@example.com", "admin")
        
        user_info = auth.get_user_info(token)
        
        assert user_info is not None
        assert user_info["user_id"] == "user123"
        assert user_info["email"] == "test@example.com"
        assert user_info["role"] == "admin"
    
    def test_invalid_token_returns_none(self):
        """Невалидный токен возвращает None."""
        from src.api.auth import JWTAuthManager
        
        auth = JWTAuthManager(secret_key="test_secret")
        
        user_info = auth.get_user_info("invalid_token_here")
        
        assert user_info is None


# ==================== Mapping Learner Tests ====================

class TestMappingLearner:
    """Тесты для Mapping Learner."""
    
    @pytest.fixture
    def learner(self, tmp_path):
        """Фикстура с временной БД."""
        from src.storage.mapping_learner import MappingLearner
        db_path = tmp_path / "test_mappings.db"
        return MappingLearner(db_path=str(db_path))
    
    def test_generate_signature_consistent(self, learner):
        """Сигнатура консистентна для одинаковых данных."""
        columns = ["Дата", "Сумма", "Контрагент"]
        
        sig1 = learner.generate_signature(columns)
        sig2 = learner.generate_signature(columns)
        
        assert sig1 == sig2
    
    def test_generate_signature_different(self, learner):
        """Сигнатура различается для разных данных."""
        columns1 = ["Дата", "Сумма"]
        columns2 = ["Дата", "Сумма", "Контрагент"]
        
        sig1 = learner.generate_signature(columns1)
        sig2 = learner.generate_signature(columns2)
        
        assert sig1 != sig2
    
    def test_save_and_get_mapping(self, learner):
        """Сохранение и получение маппинга."""
        signature = learner.generate_signature(["Колонка1", "Колонка2"])
        mapping = {
            "Колонка1": "revenue",
            "Колонка2": "date"
        }
        
        # Сохранение
        learner.save_mapping(signature, ["Колонка1", "Колонка2"], mapping)
        
        # Получение
        retrieved = learner.get_mapping(signature)
        
        assert retrieved is not None
        assert retrieved["Колонка1"] == "revenue"
        assert retrieved["Колонка2"] == "date"
    
    def test_get_nonexistent_mapping(self, learner):
        """Получение несуществующего маппинга."""
        result = learner.get_mapping("nonexistent_signature")
        
        assert result is None
    
    def test_mapping_versioning(self, learner):
        """Версионирование исправлений маппинга."""
        signature = learner.generate_signature(["Колонка1"])
        
        # Первое сохранение
        learner.save_mapping(
            signature, 
            ["Колонка1"], 
            {"Колонка1": "revenue"},
            source_type='user_confirmed'
        )
        
        # Исправление
        learner.save_mapping(
            signature,
            ["Колонка1"],
            {"Колонка1": "cost"},
            source_type='user_corrected'
        )
        
        # Должна вернуться последняя версия
        retrieved = learner.get_mapping(signature)
        
        assert retrieved is not None
        assert retrieved["Колонка1"] == "cost"
    
    def test_statistics_empty(self, learner):
        """Статистика пустой базы."""
        stats = learner.get_statistics()
        
        assert stats["total_signatures"] == 0
        assert stats["unique_mappings"] == 0
        assert stats["total_learned"] == 0
    
    def test_statistics_after_save(self, learner):
        """Статистика после сохранения."""
        signature = learner.generate_signature(["Колонка1"])
        learner.save_mapping(
            signature,
            ["Колонка1"],
            {"Колонка1": "revenue"}
        )
        
        stats = learner.get_statistics()
        
        assert stats["total_signatures"] == 1
        assert stats["unique_mappings"] >= 1
        assert stats["total_learned"] == 1
    
    def test_delete_mapping(self, learner):
        """Удаление маппинга."""
        signature = learner.generate_signature(["Колонка1"])
        learner.save_mapping(
            signature,
            ["Колонка1"],
            {"Колонка1": "revenue"}
        )
        
        # Проверка что маппинг есть
        assert learner.get_mapping(signature) is not None
        
        # Удаление
        result = learner.delete_mapping(signature)
        
        assert result == True
        
        # Проверка что маппинга нет
        assert learner.get_mapping(signature) is None
    
    def test_export_mappings(self, learner):
        """Экспорт маппингов."""
        signature = learner.generate_signature(["Колонка1", "Колонка2"])
        learner.save_mapping(
            signature,
            ["Колонка1", "Колонка2"],
            {"Колонка1": "revenue", "Колонка2": "date"}
        )
        
        exported = learner.export_mappings()
        
        assert len(exported) >= 2  # Минимум 2 записи (по одной на колонку)
        
        # Проверка структуры
        record = exported[0]
        assert "signature_hash" in record
        assert "source_column" in record
        assert "mapped_field" in record
        assert "version" in record


# Запуск тестов
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
