# Реализованные функции

## 1. Экспорт в PDF и PowerPoint

### Модуль экспорта (`src/export/`)

**PDF Exporter** (`pdf_exporter.py`):
- Генерация профессиональных PDF отчетов
- Поддержка графиков (line, bar, pie) через matplotlib
- Таблицы с данными из pandas DataFrame
- KPI карточки с метриками
- Стилизация с использованием reportlab
- Автоматическое разбиение на страницы

**PowerPoint Exporter** (`pptx_exporter.py`):
- Создание презентаций PPTX
- Титульные слайды
- KPI слайды с карточками показателей
- Графики (line, bar, pie) через python-pptx
- Таблицы данных
- Слайды с выводами и рекомендациями
- Корпоративные цвета и стили

**Использование**:
```python
from src.export import export_to_pdf, export_to_pptx

# Экспорт в PDF
pdf_path = export_to_pdf(
    metrics={"Выручка": {"value": "1.2M", "change": "+12%"}},
    charts=[{"type": "bar", "title": "Продажи", "categories": [...], "values": [...]}],
    dataframes={"Детализация": df},
    title="Аналитический отчет"
)

# Экспорт в PowerPoint
pptx_path = export_to_pptx(
    metrics={...},
    charts=[...],
    dataframes={...},
    title="Презентация для руководства",
    summary="Ключевые выводы..."
)
```

## 2. Мониторинг (Prometheus + Grafana)

### Метрики (`infrastructure/monitoring/metrics.py`)

**HTTP метрики**:
- `http_requests_total` - всего запросов
- `http_request_duration_seconds` - время ответа
- `http_requests_in_progress` - текущие запросы

**Бизнес-метрики**:
- `documents_processed_total` - обработано документов
- `parsing_duration_seconds` - время парсинга
- `exports_total` - экспорт по форматам
- `cache_hits_total/cache_misses_total` - кэш

**Health Checks**:
- Проверка здоровья компонентов
- Интеграция с Prometheus

### Docker Compose для мониторинга

**Файлы**:
- `docker-compose.monitoring.yml` - сервисы мониторинга
- `prometheus.yml` - конфигурация Prometheus
- `alerts.yml` - правила алертов
- `grafana/provisioning/` - авто-настройка Grafana
- `grafana/dashboards/app-overview.json` - дашборд приложения

**Запуск**:
```bash
cd infrastructure/monitoring
docker-compose -f docker-compose.monitoring.yml up -d
```

**Доступ**:
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin123)
- Alertmanager: http://localhost:9093
- Node Exporter: http://localhost:9100
- cAdvisor: http://localhost:8080

### Алерты

**Настроенные алерты**:
- HighErrorRate - высокая доля ошибок (>10%)
- SlowResponseTime - медленные ответы (P95 > 2s)
- HighLoad - высокая нагрузка CPU
- LowDiskSpace - мало места на диске (<10%)
- DocumentProcessingFailed - ошибки парсинга
- CacheHitRatioLow - низкий hit ratio кэша (<50%)
- ServiceDown - сервис недоступен

## 3. Резервное копирование

### Скрипт бэкапа (`infrastructure/backup/backup.sh`)

**Поддерживаемые источники**:
- PostgreSQL (pg_dump)
- Redis (RDB snapshot)
- Файлы приложения

**Функции**:
- Сжатие gzip
- Верификация целостности
- Очистка старых бэкапов (настраиваемый retention)
- Загрузка в S3 (опционально)

**Планировщик**:
```bash
# Установка cron задачи
crontab /workspace/infrastructure/backup/backup.cron

# Бэкап ежедневно в 2:00
0 2 * * * /workspace/infrastructure/backup/backup.sh
```

**Конфигурация**:
```bash
export BACKUP_DIR=/backups
export PG_HOST=localhost
export PG_DB=1c_dashboard
export RETENTION_DAYS=7
export AWS_BUCKET=my-backups  # опционально
```

## 4. Нагрузочное тестирование

### Locust тесты (`tests/test_load.py`)

**Сценарии**:
- `DashboardUser` - типичный пользователь (просмотр, загрузка, экспорт)
- `APIUser` - API интеграции (статусы, поиск, bulk операции)
- `StressUser` - стресс-тест (высокая частота запросов)

**Запуск**:
```bash
# Web UI
locust -f tests/test_load.py --host=http://localhost:8000

# Headless режим
locust -f tests/test_load.py --host=http://localhost:8000 \
  --headless --users 500 --run-time 5m

# С экспортом результатов
locust -f tests/test_load.py --host=http://localhost:8000 \
  --headless --users 200 --run-time 10m --csv results/load_test
```

**Метрики**:
- RPS (requests per second)
- Response time (avg, p50, p95, p99)
- Failure rate
- Active users

## Обновленные зависимости

Добавлены в `requirements.txt`:
```
reportlab==4.0.7          # PDF генерация
python-pptx==0.6.23       # PowerPoint генерация
prometheus-client==0.19.0 # Метрики
locust==2.20.0           # Нагрузочное тестирование
pytest-cov==4.1.0        # Coverage
```

## Структура файлов

```
/workspace
├── src/
│   └── export/
│       ├── __init__.py
│       ├── pdf_exporter.py      # PDF экспорт
│       └── pptx_exporter.py     # PowerPoint экспорт
├── infrastructure/
│   ├── monitoring/
│   │   ├── docker-compose.monitoring.yml
│   │   ├── prometheus.yml
│   │   ├── alerts.yml
│   │   ├── metrics.py
│   │   ├── grafana/
│   │   │   ├── provisioning/
│   │   │   └── dashboards/
│   │   └── alertmanager/
│   └── backup/
│       ├── backup.sh
│       └── backup.cron
└── tests/
    └── test_load.py            # Locust тесты
```

## Статус готовности

✅ **Экспорт PDF/PPTX** - полностью реализовано
✅ **Мониторинг** - Prometheus + Grafana настроены
✅ **Бэкапы** - автоматизированы с cron
✅ **Load Testing** - Locust тесты готовы

**Следующие шаги**:
1. Интегрировать экспорт в API endpoints
2. Настроить production алерты (email, Slack)
3. Добавить S3 backup в production
4. Провести нагрузочное тестирование на staging
