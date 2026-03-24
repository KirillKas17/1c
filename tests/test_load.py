"""
Расширенные нагрузочные тесты с Locust.
Сценарии: повседневная работа, стресс-тесты загрузки, API интеграции, предельная нагрузка.
"""
from locust import HttpUser, task, between, events, constant_pacing
import random
import string
import json
import time
from datetime import datetime, timedelta


class DashboardUser(HttpUser):
    """
    Сценарий: Типичный пользователь дашборда
    - Просмотр страниц, использование фильтров, экспорт отчетов
    """
    wait_time = between(2, 5)
    
    def on_start(self):
        """Инициализация: вход в систему и загрузка истории"""
        self.client.post("/auth/login", json={
            "email": "user@example.com",
            "password": "password123"
        }, catch_response=True)
        self.document_types = ["Счет", "Акт", "Накладная", "Договор", "Счет-фактура"]
        self.statuses = ["успешно", "частично", "ошибка"]
        
    @task(5)
    def view_landing(self):
        """Просмотр главной страницы (наиболее частое действие)"""
        response = self.client.get("/")
        if response.status_code != 200:
            response.failure("Landing page failed")
    
    @task(4)
    def view_dashboard(self):
        """Просмотр личного кабинета со списком документов"""
        response = self.client.get("/dashboard")
        if response.status_code != 200:
            response.failure("Dashboard failed")
    
    @task(3)
    def use_filters(self):
        """Использование фильтров: быстрые пресеты и основные фильтры"""
        # Быстрые пресеты
        presets = ["today", "week", "month", "errors_only"]
        preset = random.choice(presets)
        self.client.get(f"/api/history?preset={preset}")
        
        # Основные фильтры
        filters = {
            "search": random.choice(["ООО Ромашка", "ИНН 7701234567", "счет"]),
            "doc_type": random.choice(self.document_types),
            "status": random.choice(self.statuses),
            "sort_by": random.choice(["date_desc", "date_asc", "amount_desc", "amount_asc"])
        }
        response = self.client.get("/api/history", params=filters)
        if response.status_code != 200:
            response.failure("Filters API failed")
    
    @task(2)
    def use_advanced_filters(self):
        """Использование расширенных фильтров по дате и сумме"""
        date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        date_to = datetime.now().strftime("%Y-%m-%d")
        amount_from = random.randint(1000, 10000)
        amount_to = amount_from + random.randint(5000, 50000)
        
        filters = {
            "date_from": date_from,
            "date_to": date_to,
            "amount_from": amount_from,
            "amount_to": amount_to
        }
        response = self.client.get("/api/history", params=filters)
        if response.status_code != 200:
            response.failure("Advanced filters failed")
    
    @task(2)
    def export_pdf(self):
        """Экспорт отчета в PDF"""
        response = self.client.post("/export/pdf", json={
            "format": "pdf",
            "include_charts": True,
            "include_kpi": True
        })
        if response.status_code != 200:
            response.failure("PDF export failed")
        time.sleep(1)  # Имитация ожидания генерации
    
    @task(2)
    def export_pptx(self):
        """Экспорт презентации в PowerPoint"""
        response = self.client.post("/export/pptx", json={
            "format": "pptx",
            "include_summary": True
        })
        if response.status_code != 200:
            response.failure("PPTX export failed")
        time.sleep(1.5)
    
    @task(1)
    def view_document_details(self):
        """Просмотр деталей документа"""
        doc_id = random.randint(1, 1000)
        response = self.client.get(f"/api/documents/{doc_id}")
        if response.status_code != 200:
            response.failure(f"Document {doc_id} details failed")


class DataProcessor(HttpUser):
    """
    Сценарий: Активная загрузка и обработка документов
    Стресс-тест для системы обработки файлов
    """
    wait_time = constant_pacing(10)  # Фиксированный интервал между задачами
    
    def on_start(self):
        """Вход в систему"""
        self.client.post("/auth/login", json={
            "email": "processor@company.com",
            "password": "secure_pass"
        })
    
    @task(10)
    def upload_excel_file(self):
        """Загрузка Excel файла (тяжелая операция)"""
        file_size = random.choice([50, 100, 200, 500])  # KB
        mock_content = b"x" * (file_size * 1024)
        
        files = {
            'file': (f'data_{random.randint(1,1000)}.xlsx', mock_content, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        }
        
        start_time = time.time()
        response = self.client.post("/upload", files=files, timeout=30)
        elapsed = time.time() - start_time
        
        if response.status_code != 200:
            response.failure(f"Upload failed: {response.status_code}")
        
        # Логирование медленных запросов
        if elapsed > 5:
            print(f"⚠️ Slow upload detected: {elapsed:.2f}s for {file_size}KB")
    
    @task(5)
    def upload_pdf_file(self):
        """Загрузка PDF файла с OCR"""
        file_size = random.choice([100, 200, 500, 1000])  # KB
        mock_content = b"%" + b"PDF_MOCK_CONTENT_" + b"x" * (file_size * 1024)
        
        files = {
            'file': (f'scan_{random.randint(1,1000)}.pdf', mock_content, 'application/pdf')
        }
        
        response = self.client.post("/upload", files=files, timeout=60)
        if response.status_code != 200:
            response.failure(f"PDF upload failed: {response.status_code}")
    
    @task(3)
    def bulk_upload(self):
        """Массовая загрузка нескольких файлов"""
        for i in range(random.randint(3, 10)):
            mock_content = b"x" * (random.randint(50, 200) * 1024)
            files = {
                'file': (f'batch_{i}.xlsx', mock_content, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            }
            self.client.post("/upload", files=files, timeout=30)
            time.sleep(0.5)  # Небольшая пауза между файлами


class ApiBot(HttpUser):
    """
    Сценарий: Автоматизированная система/бот для API интеграций
    - Проверка статусов, поиск, массовые операции
    """
    wait_time = between(0.5, 2)  # Быстрые запросы
    
    @task(8)
    def check_processing_status(self):
        """Проверка статуса обработки документа"""
        task_id = f"task_{random.randint(1, 10000)}"
        response = self.client.get(f"/api/status/{task_id}")
        if response.status_code not in [200, 404]:
            response.failure(f"Status check failed: {response.status_code}")
    
    @task(6)
    def search_documents(self):
        """Поиск документов по различным критериям"""
        queries = [
            {"inn": "7701234567"},
            {"counterparty": "ООО Ромашка"},
            {"doc_number": f"№{random.randint(1, 1000)}"},
            {"date_from": "2024-01-01", "date_to": "2024-12-31"}
        ]
        query = random.choice(queries)
        response = self.client.get("/api/search", params=query)
        if response.status_code != 200:
            response.failure("Search API failed")
    
    @task(4)
    def get_analytics_summary(self):
        """Получение сводной аналитики"""
        response = self.client.get("/api/analytics/summary")
        if response.status_code != 200:
            response.failure("Analytics summary failed")
    
    @task(3)
    def get_forecast(self):
        """Запрос прогноза показателей"""
        response = self.client.get("/api/forecast", params={
            "period": random.choice(["month", "quarter", "year"]),
            "metric": random.choice(["revenue", "expenses", "profit"])
        })
        if response.status_code != 200:
            response.failure("Forecast API failed")
    
    @task(2)
    def bulk_operations(self):
        """Массовые операции с документами"""
        doc_ids = [random.randint(1, 1000) for _ in range(random.randint(5, 20))]
        response = self.client.post("/api/documents/bulk", json={
            "ids": doc_ids,
            "action": random.choice(["export", "delete", "archive"])
        })
        if response.status_code != 200:
            response.failure("Bulk operation failed")


class StressTester(HttpUser):
    """
    Сценарий: Предельная нагрузка и тестирование rate limiting
    Экстремальные условия для проверки устойчивости системы
    """
    wait_time = constant_pacing(0.1)  # Минимальные задержки
    
    @task(20)
    def rapid_requests(self):
        """Серия быстрых запросов для проверки rate limiting"""
        endpoints = [
            "/",
            "/dashboard",
            "/api/history",
            "/api/status/test_123",
            "/api/analytics/summary"
        ]
        endpoint = random.choice(endpoints)
        response = self.client.get(endpoint)
        
        # Ожидаем либо успех, либо rate limit ответ
        if response.status_code not in [200, 429, 503]:
            response.failure(f"Unexpected status: {response.status_code}")
    
    @task(10)
    def concurrent_uploads(self):
        """Попытка одновременных загрузок"""
        mock_content = b"x" * (50 * 1024)  # 50KB
        files = {'file': ('stress_test.xlsx', mock_content)}
        
        for _ in range(3):
            self.client.post("/upload", files=files, timeout=10)
            time.sleep(0.05)
    
    @task(5)
    def complex_queries(self):
        """Сложные запросы с множеством фильтров"""
        filters = {
            "search": "".join(random.choices(string.ascii_letters, k=20)),
            "doc_type": random.choice(["Счет", "Акт", "Накладная", "Договор", "Счет-фактура", "УПД"]),
            "status": random.choice(["успешно", "частично", "ошибка"]),
            "date_from": "2020-01-01",
            "date_to": "2024-12-31",
            "amount_from": 1,
            "amount_to": 1000000,
            "sort_by": random.choice(["date_desc", "date_asc", "amount_desc", "amount_asc", "name_asc", "name_desc"])
        }
        response = self.client.get("/api/history", params=filters)
        if response.status_code not in [200, 400, 429]:
            response.failure("Complex query failed")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Инициализация перед началом тестирования"""
    print("=" * 60)
    print("🚀 ЗАПУСК НАГРУЗОЧНОГО ТЕСТИРОВАНИЯ")
    print("=" * 60)
    print(f"Время начала: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Количество пользователей: {environment.runner.user_count if environment.runner else 'N/A'}")
    print("Сценарии:")
    print("  • DashboardUser - типичный пользователь")
    print("  • DataProcessor - активная загрузка файлов")
    print("  • ApiBot - API интеграции")
    print("  • StressTester - предельная нагрузка")
    print("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Завершение тестирования и вывод статистики"""
    print("\n" + "=" * 60)
    print("✅ НАГРУЗОЧНОЕ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 60)
    print(f"Время окончания: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if environment.stats:
        print("\n📊 СТАТИСТИКА:")
        print(f"  Всего запросов: {environment.stats.total.num_requests}")
        print(f"  Ошибок: {environment.stats.total.num_failures}")
        print(f"  Среднее время отклика: {environment.stats.total.avg_response_time:.2f}ms")
        print(f"  Запросов в секунду: {environment.stats.total.current_rps:.2f}")
        
        if environment.stats.total.failures:
            print("\n⚠️ ТИПЫ ОШИБОК:")
            for error in environment.stats.errors.values():
                print(f"  • {error.method} {error.name}: {error.occurrences} раз")
    
    print("=" * 60)


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Логирование медленных запросов"""
    if response_time > 3000:  # > 3 секунд
        print(f"⚠️ SLOW REQUEST: {request_type} {name} - {response_time:.0f}ms")


# Конфигурация для разных сценариев тестирования
"""
Примеры запуска:

1. Базовый тест (10 пользователей, 60 секунд):
   locust -f tests/test_load.py --headless -u 10 -r 2 --run-time 60s --host http://localhost:8000

2. Нагрузочный тест (100 пользователей, 5 минут):
   locust -f tests/test_load.py --headless -u 100 -r 10 --run-time 300s --host http://localhost:8000

3. Стресс-тест (500 пользователей, 10 минут):
   locust -f tests/test_load.py --headless -u 500 -r 50 --run-time 600s --host http://localhost:8000

4. Пиковая нагрузка (1000 пользователей):
   locust -f tests/test_load.py --headless -u 1000 -r 100 --run-time 900s --host http://localhost:8000

5. Веб-интерфейс для мониторинга:
   locust -f tests/test_load.py --web-port 8089 --host http://localhost:8000
   Затем открыть: http://localhost:8089
"""
