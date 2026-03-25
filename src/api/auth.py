"""
JWT Authentication модуль для API.

Функционал:
- Регистрация через Email/Telegram
- Login/Logout endpoints
- Refresh token rotation
- Role-based access (user, admin)
- Rate limiting (100 req/min)
"""

import jwt
import hashlib
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
from functools import wraps
import logging

logger = logging.getLogger(__name__)


def get_utc_now() -> datetime:
    """Получение текущего UTC времени (без deprecated utcnow)."""
    return datetime.now(timezone.utc)


class JWTAuthManager:
    """Управление JWT токенами и аутентификацией."""
    
    def __init__(self, secret_key: str, algorithm: str = "HS256", 
                 access_token_expire_minutes: int = 30,
                 refresh_token_expire_days: int = 7):
        """
        Инициализация JWT менеджера.
        
        Args:
            secret_key: Секретный ключ для подписи токенов
            algorithm: Алгоритм шифрования
            access_token_expire_minutes: Время жизни access токена (мин)
            refresh_token_expire_days: Время жизни refresh токена (дни)
        """
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days
        
        # Хранилище токенов (в production использовать Redis/DB)
        self.token_store: Dict[str, Dict[str, Any]] = {}
        self.blacklisted_tokens: set = set()
        
        # Rate limiting
        self.request_counts: Dict[str, list] = {}
        self.rate_limit = 100  # запросов в минуту
    
    def hash_password(self, password: str) -> str:
        """Хэширование пароля с bcrypt."""
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Проверка пароля против хэша."""
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'), 
                hashed_password.encode('utf-8')
            )
        except Exception as e:
            logger.error(f"Ошибка проверки пароля: {e}")
            return False
    
    def create_access_token(self, user_id: str, email: str, role: str = "user") -> str:
        """Создание access токена."""
        expire = get_utc_now() + timedelta(minutes=self.access_token_expire_minutes)
        
        payload = {
            "sub": user_id,
            "email": email,
            "role": role,
            "type": "access",
            "exp": expire,
            "iat": get_utc_now(),
            "jti": hashlib.md5(f"{user_id}{get_utc_now()}".encode()).hexdigest()
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        logger.info(f"Access токен создан для пользователя {user_id}")
        return token
    
    def create_refresh_token(self, user_id: str) -> str:
        """Создание refresh токена."""
        expire = get_utc_now() + timedelta(days=self.refresh_token_expire_days)
        
        payload = {
            "sub": user_id,
            "type": "refresh",
            "exp": expire,
            "iat": get_utc_now(),
            "jti": hashlib.md5(f"{user_id}{get_utc_now()}{expire}".encode()).hexdigest()
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        # Сохраняем токен в хранилище
        self.token_store[token] = {
            "user_id": user_id,
            "created_at": get_utc_now(),
            "expires_at": expire
        }
        
        logger.info(f"Refresh токен создан для пользователя {user_id}")
        return token
    
    def verify_token(self, token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """
        Верификация токена.
        
        Args:
            token: JWT токен
            token_type: Тип токена (access или refresh)
            
        Returns:
            Payload токена или None если невалиден
        """
        # Проверка на blacklist
        if token in self.blacklisted_tokens:
            logger.warning(f"Токен в blacklist: {token[:20]}...")
            return None
        
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Проверка типа токена
            if payload.get("type") != token_type:
                logger.warning(f"Неверный тип токена: {payload.get('type')}")
                return None
            
            # Проверка срока действия
            exp = payload.get("exp")
            if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < get_utc_now():
                logger.warning("Токен истёк")
                return None
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Токен истёк (ExpiredSignatureError)")
            return None
        except jwt.InvalidTokenError as e:
            logger.error(f"Невалидный токен: {e}")
            return None
    
    def refresh_access_token(self, refresh_token: str) -> Optional[Tuple[str, str]]:
        """
        Обновление access токена по refresh токену.
        
        Returns:
            Кортеж (new_access_token, new_refresh_token) или None
        """
        payload = self.verify_token(refresh_token, token_type="refresh")
        
        if not payload:
            return None
        
        user_id = payload.get("sub")
        
        # Проверка токена в хранилище
        if refresh_token not in self.token_store:
            logger.warning("Refresh токен не найден в хранилище")
            return None
        
        # Rotation: инвалидация старого refresh токена
        self.blacklist_token(refresh_token)
        
        # Создание новых токенов
        # В реальном приложении нужно получить email и role из БД
        new_access = self.create_access_token(user_id, f"user_{user_id}@example.com")
        new_refresh = self.create_refresh_token(user_id)
        
        logger.info(f"Токены обновлены для пользователя {user_id}")
        return (new_access, new_refresh)
    
    def blacklist_token(self, token: str) -> None:
        """Добавление токена в blacklist."""
        self.blacklisted_tokens.add(token)
        
        # Удаление из хранилища если есть
        if token in self.token_store:
            del self.token_store[token]
        
        logger.debug(f"Токен добавлен в blacklist: {token[:20]}...")
    
    def logout(self, access_token: str, refresh_token: str = None) -> None:
        """Logout пользователя (инвалидация всех токенов)."""
        self.blacklist_token(access_token)
        
        if refresh_token:
            self.blacklist_token(refresh_token)
        
        logger.info("Пользователь вышел из системы")
    
    def check_rate_limit(self, user_id: str) -> bool:
        """
        Проверка rate limiting.
        
        Returns:
            True если запрос разрешён, False если превышен лимит
        """
        now = get_utc_now()
        minute_ago = now - timedelta(minutes=1)
        
        # Получение истории запросов пользователя
        if user_id not in self.request_counts:
            self.request_counts[user_id] = []
        
        # Очистка старых записей
        self.request_counts[user_id] = [
            ts for ts in self.request_counts[user_id] 
            if ts > minute_ago
        ]
        
        # Проверка лимита
        if len(self.request_counts[user_id]) >= self.rate_limit:
            logger.warning(f"Rate limit превышен для пользователя {user_id}")
            return False
        
        # Добавление текущего запроса
        self.request_counts[user_id].append(now)
        return True
    
    def get_user_info(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Получение информации о пользователе из токена."""
        payload = self.verify_token(access_token, token_type="access")
        
        if not payload:
            return None
        
        return {
            "user_id": payload.get("sub"),
            "email": payload.get("email"),
            "role": payload.get("role")
        }
    
    def require_auth(self, required_role: str = None):
        """
        Декоратор для защиты endpoints.
        
        Args:
            required_role: Требуемая роль (None = любая авторизованная)
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # В реальном приложении токен берётся из заголовков запроса
                token = kwargs.get('access_token')
                
                if not token:
                    return {"error": "Требуется аутентификация"}, 401
                
                user_info = self.get_user_info(token)
                
                if not user_info:
                    return {"error": "Невалидный токен"}, 401
                
                # Проверка роли
                if required_role and user_info.get("role") != required_role:
                    return {"error": "Недостаточно прав"}, 403
                
                # Проверка rate limiting
                if not self.check_rate_limit(user_info["user_id"]):
                    return {"error": "Превышен лимит запросов"}, 429
                
                # Добавление user_info в контекст
                kwargs['current_user'] = user_info
                return func(*args, **kwargs)
            
            return wrapper
        return decorator


# Singleton instance
_auth_manager: Optional[JWTAuthManager] = None


def get_auth_manager(secret_key: str = None) -> JWTAuthManager:
    """Получение singleton экземпляра JWTAuthManager."""
    global _auth_manager
    
    if _auth_manager is None:
        if not secret_key:
            # Default key для development (в production использовать env variable!)
            secret_key = "your-secret-key-change-in-production"
        
        _auth_manager = JWTAuthManager(secret_key=secret_key)
    
    return _auth_manager
