# 1C Dashboard Service 📊

Автоматизированная система построения дашбордов и прогнозирования на основе данных из 1С.

## 🚀 Возможности

- **Загрузка файлов**: XLSX/XLS/CSV из 1С
- **AI-детекция**: Автоматическое распознавание структуры данных
- **45+ бизнес-правил**: Для ритейла, производства, финансов, услуг
- **Прогнозирование**: 5 методов ML (Prophet, XGBoost, Ensemble)
- **Экспорт**: PDF и PowerPoint отчеты
- **REST API**: Полноценное FastAPI приложение

## 📦 Быстрый старт

### Через Docker Compose (рекомендуется)

```bash
# Клонировать репозиторий
git clone https://github.com/your-org/onec-dashboard.git
cd onec-dashboard

# Скопировать .env.example в .env
cp .env.example .env

# Запустить все сервисы
docker-compose up -d

# Проверить статус
docker-compose ps

# Просмотреть логи
docker-compose logs -f api
```

Приложение доступно по адресу: http://localhost:8000
API документация: http://localhost:8000/docs

### Локальная разработка

```bash
# Установить зависимости
pip install -r requirements.txt

# Запустить PostgreSQL (через Docker)
docker run -d --name postgres \
  -e POSTGRES_DB=onec_dashboard \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  postgres:16-alpine

# Применить миграции
alembic upgrade head

# Запустить сервер
uvicorn src.api.main:create_app --factory --reload
```

## 🔧 Конфигурация

Основные переменные окружения (см. `.env.example`):

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `DATABASE_URL` | PostgreSQL connection string | postgresql+asyncpg://... |
| `SECRET_KEY` | JWT secret key (мин. 32 символа) | - |
| `ENVIRONMENT` | development/staging/production | development |
| `DEBUG` | Режим отладки | true |
| `UPLOAD_DIR` | Директория для загрузок | ./uploads |

## 📚 API Endpoints

### Аутентификация
- `POST /api/v1/auth/register` - Регистрация
- `POST /api/v1/auth/login` - Вход
- `GET /api/v1/auth/me` - Профиль пользователя

### Файлы
- `POST /api/v1/files/upload` - Загрузка файла
- `GET /api/v1/files/{id}/status` - Статус обработки

### Дашборды
- `POST /api/v1/dashboard/create` - Создание дашборда
- `GET /api/v1/dashboard/{id}` - Получение дашборда
- `GET /api/v1/dashboard/export/pdf` - Экспорт в PDF

### Прогнозирование
- `POST /api/v1/forecast/run` - Запуск прогноза
- `GET /api/v1/forecast/{id}` - Результаты прогноза

## 🏗️ Архитектура

```
src/
├── api/           # FastAPI приложение
│   ├── main.py    # Точка входа
│   ├── auth.py    # JWT аутентификация
│   ├── config.py  # Конфигурация
│   ├── db/        # Database layer
│   └── models/    # SQLAlchemy модели
├── core/          # Бизнес-логика
│   ├── parser.py              # Парсер Excel/CSV
│   ├── ai_detector.py         # AI детекция структуры
│   ├── business_rules_engine.py # Бизнес-правила
│   └── forecasting.py         # ML прогнозирование
├── export/        # Экспорт отчетов
│   ├── pdf_exporter.py
│   └── pptx_exporter.py
└── schemas/       # Pydantic схемы
```

## 🧪 Тестирование

```bash
# Запустить тесты
pytest tests/ -v

# С coverage
pytest tests/ -v --cov=src --cov-report=html
```

## 📈 Мониторинг

- **Metrics**: http://localhost:8000/metrics (Prometheus format)
- **Health Check**: http://localhost:8000/health

## 🔐 Безопасность

- JWT токены (access + refresh)
- Rate limiting (60 запросов/мин)
- Валидация входных данных
- Audit логирование всех действий
- HTTPS в production (требуется настройка SSL)

## 📄 Лицензия

MIT License

## 🤝 Поддержка

Email: support@onecdashboard.ru
Docs: https://docs.onecdashboard.ru
