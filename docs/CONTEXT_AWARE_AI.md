# 🧠 CONTEXT-AWARE AI ARCHITECTURE

## Проблема, которую мы решили
Раньше система строила **одинаковую аналитику** для автосервиса и столярного производства. Это неправильно: 
- Автосервису важны: загрузка постов, средний чек, повторные клиенты
- Столярке важны: процент брака, расход материалов, сроки выполнения заказов

## Решение: "Магический" AI без настроек от пользователя

Пользователь просто загружает файл → Система сама понимает бизнес → Строит правильные метрики.

---

## 🏗 Архитектура работы

### Этап 1: Извлечение данных (Parser)
```python
# Читаем только заголовки + первые 3 значения из каждой колонки
columns = ["Дата", "Услуга", "Сумма", "Клиент", "Статус"]
samples = {
    "Дата": ["2024-01-15", "2024-01-16"],
    "Услуга": ["Замена масла", "Диагностика"],
    "Сумма": [5000, 1500],
    ...
}
```
**Зачем:** Минимум токенов для LLM, максимум информации.

---

### Этап 2: Детекция отрасли (LLM)
Отправляем в LLM промпт:
```
Проанализируй структуру данных:
- Колонки: [Дата, Услуга, Сумма, Клиент, Статус]
- Примеры: ["Замена масла", "Диагностика"]

Задача:
1. Определи тип бизнеса (будь конкретен: не просто "Сервис", а "Автосервис")
2. Назови 5-7 главных KPI для владельца
3. Какие риски критичны для этой отрасли?
4. Как правильно интерпретировать данные?
```

**Ответ LLM (JSON):**
```json
{
  "industry_type": "Auto Repair Shop",
  "confidence_score": 0.94,
  "key_metrics": [
    "Average Repair Order Value",
    "Technician Utilization Rate",
    "Repeat Customer Rate",
    "Days in Repair",
    "Parts Margin"
  ],
  "critical_alerts": [
    "High comeback rate (warranty returns)",
    "Low technician efficiency",
    "Negative gross profit on labor"
  ],
  "business_logic_hints": [
    "Labor sales should exceed parts sales by 1.5x",
    "Comeback rate > 3% is critical",
    "Check for negative margins on warranty work"
  ],
  "suggested_dashboard_focus": "Focus on technician productivity and repeat customer retention."
}
```

---

### Этап 3: Динамическая подстройка правил (Rule Injection)

Система получает контекст от LLM и **адаптирует** Business Rules Engine:

```python
context = {
    "industry": "Auto Repair Shop",
    "priority_metrics": ["Technician Utilization", "Comeback Rate"],
    "critical_alerts": ["High comeback rate"],
    "logic_hints": ["Comeback rate > 3% is critical"]
}

# Запускаем анализ с учетом контекста
results = rules_engine.run_full_analysis(
    data=df,
    context=context  # ← Ключевой момент!
)
```

**Что меняется внутри Rules Engine:**
- Стандартное правило: "Проверь аномалии" → **Контекстное**: "Проверь % возвратов (Comeback Rate), если > 3% — КРИТИЧНО"
- Стандартный прогноз: "Тренд выручки" → **Контекстный**: "Прогноз загрузки постов + маржинальность нормо-часа"

---

### Этап 4: Генерация отчета

Формируем финальный JSON с **отраслевым фокусом**:

```json
{
  "industry_context": {
    "type": "Auto Repair Shop",
    "dashboard_focus": "Focus on technician productivity..."
  },
  "analysis": {
    "kpi": {
      "technician_utilization": 78%,  // ← Главный KPI для автосервиса
      "comeback_rate": 2.1%,          // ← В норме (< 3%)
      "avg_repair_order": 12500
    },
    "alerts": [
      {
        "level": "warning",
        "message": "Technician utilization below 85% target",
        "industry_benchmark": "Top shops achieve 90%+"
      }
    ]
  },
  "recommendations": [
    "Focus on tracking: Technician Utilization, Comeback Rate, Avg Repair Order as they are critical for Auto Repair Shop."
  ]
}
```

---

## 📁 Файловая структура

```
src/
├── core/
│   └── industry_context.py       # ← Новый модуль: IndustryContextEngine
│       ├── IndustryInsight (Pydantic model)
│       └── analyze_structure()   # Вызов LLM для детекции
│
├── api/services/
│   └── context_analysis_service.py  # ← Оркестратор всего процесса
│       ├── parse_file()
│       ├── detect_industry()     # Вызов industry_context
│       ├── inject_rules()        # Передача контекста в Rules Engine
│       └── generate_report()
│
└── api/routes/
    └── upload.py                 # Обновленный endpoint /api/v1/upload
        └── POST /upload → вызывает context_analysis_service
```

---

## 🔑 Ключевые преимущества

| Было | Стало |
|------|-------|
| Одинаковые метрики для всех | **Уникальные KPI** для каждой отрасли |
| Пользователь выбирает отрасль | **AI сам определяет** по заголовкам |
| Жесткие правила | **Динамическая подстройка** под контекст |
| Общие рекомендации | **Конкретные советы** для бизнеса |

---

## 🚀 Как это работает на примерах

### Пример 1: Автосервис
**Загруженные колонки:** `["Дата", "Пост", "Механик", "Услуга", "Нормо-часы", "Запчасти"]`

**LLM определяет:**
- Отрасль: `Auto Repair Shop`
- KPI: `Utilization Rate`, `Efficiency`, `Comeback Rate`
- Алерты: `Высокий % возвратов`, `Простой постов`

**Результат:** Дашборд с загрузкой постов и эффективностью механиков.

---

### Пример 2: Столярное производство
**Загруженные колонки:** `["Дата", "Изделие", "Материал", "Брак", "Время_изготовления"]`

**LLM определяет:**
- Отрасль: `Woodworking Manufacturing`
- KPI: `Defect Rate`, `Material Yield`, `Cycle Time`
- Алерты: `Высокий % брака`, `Перерасход материала`

**Результат:** Дашборд с % брака и расходом материалов.

---

### Пример 3: Розничный магазин
**Загруженные колонки:** `["Чек", "Товар", "Количество", "Скидка", "Возврат"]`

**LLM определяет:**
- Отрасль: `Retail Store`
- KPI: `Average Transaction Value`, `Return Rate`, `Inventory Turnover`
- Алерты: `Высокий % возвратов`, `Низкая оборачиваемость`

**Результат:** Дашборд с возвратами и оборачиваемостью.

---

## 🎯 Итог

**Пользовательский опыт:**
1. Загрузил файл из 1С
2. Через 10 секунд получил **релевантный именно его бизнесу** дашборд
3. Никаких настроек, вопросов, выбора отрасли

**Техническая магия:**
- LLM анализирует заголовки → Определяет отрасль → Подстраивает правила → Генерирует отчет
- Всё автоматически, без участия человека

**Это и есть Autonomous Analytics уровня Enterprise SaaS.** 🚀
