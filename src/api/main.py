"""
Главное FastAPI приложение 1C Dashboard Service

Маршруты:
- /api/v1/auth/* - Аутентификация
- /api/v1/files/* - Загрузка файлов
- /api/v1/dashboard/* - Дашборды и аналитика
- /api/v1/payments/* - Оплата и подписки
- /health - Health check
"""
from fastapi import FastAPI, Depends, HTTPException, status, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from contextlib import asynccontextmanager
import logging
from datetime import datetime, timezone
from typing import Optional
import os
import uuid

from .config import settings
from .auth import get_auth_manager, JWTAuthManager
from ..schemas.models import (
    UserCreate, UserLogin, Token, UserResponse,
    FileUploadResponse, FileStatusResponse,
    DashboardConfig, DashboardResponse,
    PaymentIntent, PaymentWebhook, SubscriptionPlan,
    HealthCheck
)
from ..core.parser import ExcelParser
from ..core.ai_detector import AIDetector
from ..core.forecasting import ForecastEngine
from ..core.business_rules_engine import BusinessRulesEngine
from ..export.pdf_exporter import PDFExporter
from ..export.pptx_exporter import PowerPointExporter

# Database imports
from .db.database import init_db, close_db, get_db
from .models.models import User, UploadedFile, Dashboard, Forecast, AuditLog, SubscriptionTier
from sqlalchemy.ext.asyncio import AsyncSession

# Monitoring
from prometheus_fastapi_instrumentator import PrometheusFastApiInstrumentator

# Логирование
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# === Lifespan Events ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Инициализация и завершение работы приложения"""
    # Startup
    logger.info(f"🚀 Запуск {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Окружение: {settings.ENVIRONMENT}")
    
    # Инициализация базы данных
    try:
        await init_db()
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.warning(f"⚠️ База данных недоступна: {e}. Работа в demo режиме.")
    
    # Инициализация сервисов
    app.state.auth_manager = get_auth_manager(settings.SECRET_KEY)
    app.state.parser = ExcelParser()
    app.state.ai_detector = AIDetector()
    app.state.forecast_engine = ForecastEngine()
    app.state.business_rules = BusinessRulesEngine()
    app.state.pdf_exporter = PDFExporter()
    app.state.pptx_exporter = PowerPointExporter()
    
    # Хранилища (в production заменить на Redis/DB)
    app.state.files = {}  # file_id -> file_info
    app.state.dashboards = {}  # dashboard_id -> dashboard_data
    app.state.subscriptions = {}  # user_id -> subscription_info
    
    # Создание директории для загрузок
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    
    logger.info("✅ Все сервисы инициализированы")
    logger.info("✅ Приложение готово к работе")
    
    yield
    
    # Shutdown
    logger.info("👋 Завершение работы приложения")
    await close_db()


# === Application Factory ===

def create_app() -> FastAPI:
    """Создание и настройка FastAPI приложения"""
    
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="""
## 1C Dashboard Service API

Автоматизированная система построения дашбордов на основе данных из 1С.

### Возможности:
- **Загрузка файлов** XLSX/XLS/CSV из 1С
- **AI-детекция** структуры данных
- **45+ бизнес-правил** для различных отраслей
- **Прогнозирование** методами ML (Prophet, XGBoost, Ensemble)
- **Экспорт** в PDF и PowerPoint
- **Гибкие тарифы** от 990₽/мес

### Тарифы:
- **Starter**: 990₽/мес - до 5 дашбордов
- **Professional**: 4900₽/мес - безлимит + приоритет
- **Enterprise**: 19900₽/мес - white-label + SLA
        """,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan
    )
    
    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Prometheus Monitoring
    if settings.ENVIRONMENT != "testing":
        PrometheusFastApiInstrumentator(
            should_respect_env_var=True,
            should_instrument_requests_inprogress=True,
        ).instrument(app).expose(app, endpoint="/metrics")
    
    # Register routes
    register_routes(app)
    
    return app


# === Routes Registration ===

def register_routes(app: FastAPI):
    """Регистрация всех маршрутов"""
    
    # === Helper Functions (должны быть определены до использования) ===
    
    async def get_current_user_optional(request: Request) -> Optional[dict]:
        """Получение текущего пользователя (опционально)"""
        auth_header = request.headers.get("Authorization")
        
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        
        token = auth_header.split(" ")[1]
        auth_manager: JWTAuthManager = request.app.state.auth_manager
        
        user_info = auth_manager.get_user_info(token)
        return user_info
    
    async def get_current_user_required(request: Request) -> dict:
        """Получение текущего пользователя (обязательно)"""
        auth_header = request.headers.get("Authorization")
        
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Требуется аутентификация",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        token = auth_header.split(" ")[1]
        auth_manager: JWTAuthManager = request.app.state.auth_manager
        
        user_info = auth_manager.get_user_info(token)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Невалидный токен",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Проверка rate limiting
        if not auth_manager.check_rate_limit(user_info["user_id"]):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Превышен лимит запросов"
            )
        
        return user_info
    
    # === Health Check ===
    
    @app.get("/health", response_model=HealthCheck, tags=["Health"])
    async def health_check():
        """Проверка здоровья сервиса"""
        return HealthCheck(
            status="healthy",
            version=settings.APP_VERSION,
            timestamp=datetime.now(timezone.utc),
            services={
                "api": "ok",
                "parser": "ok",
                "ai_detector": "ok",
                "forecasting": "ok",
            }
        )
    
    # === Auth Endpoints ===
    
    @app.post("/api/v1/auth/register", response_model=UserResponse, tags=["Authentication"])
    async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
        """Регистрация нового пользователя с автоматическим запуском триала"""
        from src.api.services.trial_service import TrialService
        
        logger.info(f"Регистрация пользователя: {user_data.email}")
        
        auth_manager: JWTAuthManager = app.state.auth_manager
        
        # Хэширование пароля
        hashed_password = auth_manager.hash_password(user_data.password)
        
        # Проверка существования пользователя (в production через БД)
        # Здесь mock для демонстрации
        user_id = f"user_{hash(user_data.email)}"
        
        # Создание пользователя в БД (если подключена)
        try:
            new_user = User(
                email=user_data.email,
                hashed_password=hashed_password,
                full_name=user_data.full_name,
                company_name=user_data.company_name,
                subscription_tier=SubscriptionTier.TRIAL
            )
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            
            # Запуск триала
            trial_service = TrialService(db)
            trial_info = await trial_service.start_trial(new_user)
            
            logger.info(f"Триал запущен для пользователя {new_user.id}: {trial_info}")
            
        except Exception as e:
            logger.warning(f"БД недоступна, работа в demo режиме: {e}")
            # Demo режим без БД
        
        return UserResponse(
            id=hash(user_id) % 100000,
            email=user_data.email,
            full_name=user_data.full_name,
            company_name=user_data.company_name,
            subscription_tier="trial",
            subscription_expires=datetime.now(timezone.utc).replace(day=datetime.now().day + 14),
            created_at=datetime.now(timezone.utc),
            is_active=True,
            trial_info={
                "trial_started": datetime.now(timezone.utc).isoformat(),
                "trial_ends": (datetime.now(timezone.utc).replace(day=datetime.now().day + 14)).isoformat(),
                "limits": {
                    "reports_total": 10,
                    "templates": 3,
                    "files": 5,
                    "reports_per_day": 3
                }
            } if settings.DEBUG else None
        )
    
    @app.post("/api/v1/auth/login", response_model=Token, tags=["Authentication"])
    async def login(credentials: UserLogin):
        """Вход в систему и получение токенов"""
        auth_manager: JWTAuthManager = app.state.auth_manager
        
        # В production: проверка credentials в БД
        # Здесь mock для демонстрации
        logger.info(f"Вход пользователя: {credentials.email}")
        
        # Mock проверка (в production реальная проверка пароля)
        user_id = f"user_{hash(credentials.email)}"
        
        # Создание токенов
        access_token = auth_manager.create_access_token(
            user_id=user_id,
            email=credentials.email,
            role="user"
        )
        
        refresh_token = auth_manager.create_refresh_token(user_id)
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    
    @app.post("/api/v1/auth/refresh", response_model=Token, tags=["Authentication"])
    async def refresh_token(refresh_token: str):
        """Обновление access токена"""
        auth_manager: JWTAuthManager = app.state.auth_manager
        
        result = auth_manager.refresh_access_token(refresh_token)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Невалидный refresh токен"
            )
        
        new_access, new_refresh = result
        
        return Token(
            access_token=new_access,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    
    @app.post("/api/v1/auth/logout", tags=["Authentication"])
    async def logout(
        access_token: str,
        current_user: dict = Depends(get_current_user_optional)
    ):
        """Выход из системы"""
        auth_manager: JWTAuthManager = app.state.auth_manager
        auth_manager.logout(access_token)
        
        return {"message": "Успешный выход"}
    
    @app.get("/api/v1/auth/me", response_model=UserResponse, tags=["Authentication"])
    async def get_current_user_profile(
        current_user: dict = Depends(get_current_user_required)
    ):
        """Получение профиля текущего пользователя"""
        # В production: загрузка из БД
        user_id_int = abs(hash(current_user["user_id"])) % 100000
        return UserResponse(
            id=user_id_int,
            email=current_user["email"],
            company_name="Demo Company",
            subscription_tier="starter",
            subscription_expires=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            is_active=True
        )
    
    # === File Upload Endpoints ===
    
    @app.post("/api/v1/files/upload", response_model=FileUploadResponse, tags=["Files"])
    async def upload_file(
        request: Request,
        file: UploadFile = File(..., description="Файл Excel/CSV из 1С"),
        current_user: dict = Depends(get_current_user_required)
    ):
        """Загрузка файла с данными 1С"""
        logger.info(f"Загрузка файла пользователем {current_user['email']}: {file.filename}")
        
        # Валидация типа файла
        allowed_extensions = {".xlsx", ".xls", ".csv"}
        file_ext = os.path.splitext(file.filename)[0].lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Неподдерживаемый формат файла. Разрешены: {', '.join(allowed_extensions)}"
            )
        
        # Создание уникального имени файла
        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
        
        # Сохранение файла
        try:
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
        except Exception as e:
            logger.error(f"Ошибка сохранения файла: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при сохранении файла"
            )
        
        # Парсинг файла
        try:
            parser: ExcelParser = request.app.state.parser
            result = parser.parse_file(file_path)
            
            # AI детекция структуры
            ai_detector: AIDetector = request.app.state.ai_detector
            ai_result = ai_detector.detect(result["data"])
            
            file_id = f"file_{uuid.uuid4().hex[:12]}"
            
            # Сохранение информации о файле
            file_info = {
                "file_id": file_id,
                "file_path": file_path,
                "filename": file.filename,
                "user_id": current_user["user_id"],
                "rows_count": len(result["data"]),
                "columns_count": len(result["data"].columns) if len(result["data"]) > 0 else 0,
                "detected_format": file_ext[1:],
                "ai_structure": ai_result,
                "upload_timestamp": datetime.now(timezone.utc),
                "status": "ready"
            }
            
            request.app.state.files[file_id] = file_info
            
            return FileUploadResponse(
                file_id=file_id,
                filename=file.filename,
                size_bytes=len(content),
                rows_count=file_info["rows_count"],
                columns_count=file_info["columns_count"],
                detected_format=file_ext[1:],
                upload_timestamp=file_info["upload_timestamp"],
                status="ready"
            )
            
        except Exception as e:
            logger.error(f"Ошибка обработки файла: {e}")
            # Удаление файла при ошибке
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка при обработке файла: {str(e)}"
            )
    
    @app.get("/api/v1/files/{file_id}/status", response_model=FileStatusResponse, tags=["Files"])
    async def get_file_status(
        file_id: str,
        request: Request,
        current_user: dict = Depends(get_current_user_required)
    ):
        """Проверка статуса обработки файла"""
        files_storage = request.app.state.files
        
        if file_id not in files_storage:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Файл не найден"
            )
        
        file_info = files_storage[file_id]
        
        # Проверка прав доступа
        if file_info["user_id"] != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет доступа к этому файлу"
            )
        
        return FileStatusResponse(
            file_id=file_id,
            status=file_info["status"],
            progress=100 if file_info["status"] == "ready" else 50,
            result={
                "metrics_detected": len(file_info.get("ai_structure", {}).get("metrics", [])),
                "charts_generated": len(file_info.get("ai_structure", {}).get("recommended_charts", [])),
                "forecasts_created": len(file_info.get("ai_structure", {}).get("forecastable_columns", []))
            }
        )
    
    # === Dashboard Endpoints ===
    
    @app.post("/api/v1/dashboard/create", response_model=DashboardResponse, tags=["Dashboards"])
    async def create_dashboard(
        request: Request,
        file_id: str,
        config: Optional[DashboardConfig] = None,
        current_user: dict = Depends(get_current_user_required)
    ):
        """Создание дашборда на основе загруженного файла"""
        logger.info(f"Создание дашборда для пользователя {current_user['email']}")
        
        # Проверка существования файла
        files_storage = request.app.state.files
        if file_id not in files_storage:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Файл не найден. Сначала загрузите файл."
            )
        
        file_info = files_storage[file_id]
        
        # Проверка прав доступа
        if file_info["user_id"] != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет доступа к этому файлу"
            )
        
        try:
            # Загрузка данных
            parser: ExcelParser = request.app.state.parser
            result = parser.parse_file(file_info["file_path"])
            data = result["data"]
            
            # AI детекция структуры
            ai_detector: AIDetector = request.app.state.ai_detector
            ai_result = ai_detector.detect(data)
            
            # Применение бизнес-правил
            business_rules: BusinessRulesEngine = request.app.state.business_rules
            rules_result = business_rules.apply_all(data)
            
            # Прогнозирование
            forecast_engine: ForecastEngine = request.app.state.forecast_engine
            forecasts = []
            for col in ai_result.get("forecastable_columns", [])[:3]:  # Максимум 3 прогноза
                try:
                    forecast = forecast_engine.forecast(data, target_column=col, periods=12)
                    forecasts.append({
                        "metric": col,
                        "periods": 12,
                        "values": forecast.get("forecast", []),
                        "confidence_lower": forecast.get("confidence_lower", []),
                        "confidence_upper": forecast.get("confidence_upper", []),
                        "method": forecast.get("method", "naive")
                    })
                except Exception as e:
                    logger.warning(f"Не удалось создать прогноз для {col}: {e}")
            
            # Генерация метрик
            metrics = []
            for metric_name, metric_info in ai_result.get("metrics", {}).items():
                metrics.append({
                    "name": metric_name,
                    "value": float(metric_info.get("current_value", 0)),
                    "trend": metric_info.get("trend", "stable"),
                    "change_percent": float(metric_info.get("change_percent", 0))
                })
            
            # Генерация инсайтов
            insights = rules_result.get("insights", [])[:5]  # Максимум 5 инсайтов
            recommendations = rules_result.get("recommendations", [])[:5]
            
            dashboard_id = f"dash_{uuid.uuid4().hex[:12]}"
            
            # Сохранение дашборда
            dashboard_data = {
                "dashboard_id": dashboard_id,
                "file_id": file_id,
                "user_id": current_user["user_id"],
                "title": "Аналитический дашборд",
                "created_at": datetime.now(timezone.utc),
                "metrics": metrics,
                "charts": ai_result.get("recommended_charts", []),
                "forecasts": forecasts,
                "insights": insights,
                "recommendations": recommendations
            }
            
            request.app.state.dashboards[dashboard_id] = dashboard_data
            
            return DashboardResponse(**dashboard_data)
            
        except Exception as e:
            logger.error(f"Ошибка создания дашборда: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка при создании дашборда: {str(e)}"
            )
    
    @app.get("/api/v1/dashboard/{dashboard_id}", response_model=DashboardResponse, tags=["Dashboards"])
    async def get_dashboard(
        dashboard_id: str,
        current_user: dict = Depends(get_current_user_required)
    ):
        """Получение данных дашборда"""
        # В production: загрузка из БД
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Дашборд не найден"
        )
    
    # === Payment Endpoints ===
    
    @app.get("/api/v1/payments/plans", response_model=list[SubscriptionPlan], tags=["Payments"])
    async def get_subscription_plans():
        """Получение доступных тарифных планов"""
        return [
            SubscriptionPlan(
                tier="starter",
                price=990,
                features=[
                    "До 5 дашбордов",
                    "Базовое прогнозирование",
                    "Экспорт в PNG",
                    "Поддержка по email"
                ],
                limits={"dashboards": 5, "users": 1, "storage_gb": 1}
            ),
            SubscriptionPlan(
                tier="professional",
                price=4900,
                features=[
                    "Безлимитные дашборды",
                    "Продвинутое прогнозирование (ML)",
                    "Экспорт в PDF/PPTX",
                    "Приоритетная поддержка",
                    "API доступ"
                ],
                limits={"dashboards": -1, "users": 5, "storage_gb": 50}
            ),
            SubscriptionPlan(
                tier="enterprise",
                price=19900,
                features=[
                    "White-label решение",
                    "Персональный менеджер",
                    "SLA 99.9%",
                    "Кастомные интеграции",
                    "Обучение сотрудников"
                ],
                limits={"dashboards": -1, "users": -1, "storage_gb": 500}
            ),
        ]
    
    @app.post("/api/v1/payments/create-intent", response_model=PaymentIntent, tags=["Payments"])
    async def create_payment_intent(
        plan_tier: str,
        current_user: dict = Depends(get_current_user_required)
    ):
        """Создание платежного намерения (YooKassa)"""
        logger.info(f"Создание платежа для {current_user['email']}, тариф: {plan_tier}")
        
        # В production: создание платежа через YooKassa API
        payment_id = f"pay_{datetime.now(timezone.utc).timestamp()}"
        
        prices = {"starter": 990, "professional": 4900, "enterprise": 19900}
        amount = prices.get(plan_tier, 990)
        
        return PaymentIntent(
            payment_id=payment_id,
            amount=amount,
            currency="RUB",
            description=f"Подписка {plan_tier}",
            customer_email=current_user["email"],
            return_url=settings.YOOKASSA_RETURN_URL,
            status="pending"
        )
    
    @app.post("/api/v1/payments/webhook", tags=["Payments"])
    async def payment_webhook(webhook_data: PaymentWebhook):
        """Обработка webhook от платежной системы (YooKassa)"""
        logger.info(f"Получен webhook: {webhook_data.event_type}")
        
        # В production: верификация подписи, обновление статуса подписки в БД
        if webhook_data.event_type == "payment.succeeded":
            # Активация подписки
            pass
        elif webhook_data.event_type == "payment.canceled":
            # Отмена подписки
            pass
        
        return {"status": "ok"}
    

# === Create App Instance ===

app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.api.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else settings.WORKERS
    )
