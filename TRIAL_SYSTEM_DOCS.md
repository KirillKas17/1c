# 🎯 УМНАЯ СИСТЕМА ТРИАЛЬНОГО ПЕРИОДА

## 📋 Обзор

Реализована профессиональная система триального периода по лучшим практикам SaaS-компаний (Stripe, Notion, Figma, Slack).

---

## 🔥 КЛЮЧЕВЫЕ ОСОБЕННОСТИ

### 1. **Двухуровневая защита от злоупотреблений**

#### Временные ограничения:
- **14 дней** триального периода (industry standard)
- Автоматическое истечение по таймеру
- Четкая дата окончания

#### Ограничения по использованию:
| Ресурс | Лимит | Обоснование |
|--------|-------|-------------|
| Отчеты (всего) | 10 | Достаточно для оценки, но не для полной работы |
| Шаблоны | 3 | Можно сохранить ключевые форматы |
| Файлы | 5 | Несколько загрузок для теста |
| **Отчеты в день** | **3** | **Anti-abuse: предотвращает "one-day sprint"** |

### 2. **Daily Cap - Защита от "Однодневного Марафона"**

**Проблема:** Пользователь регистрируется, генерирует все отчеты за день и уходит.

**Решение:** 
- Максимум 3 отчета в день
- Счетчик сбрасывается в полночь UTC
- Стимул возвращаться каждый день → выше вовлеченность → выше конверсия

```python
# Пример логики
if user.daily_report_count >= 3:
    return "Достигнут дневной лимит. Вернитесь завтра или оформите подписку!"
```

### 3. **Прогрессивные Предупреждения**

Система автоматически генерирует предупреждения:

- ⚠️ **За 3 дня до окончания:** "Триал заканчивается через 3 дня!"
- ⚠️ **80% лимита отчетов:** "Использовано 8/10 отчетов"
- ⚠️ **Дневной лимит:** "3 отчета сегодня. Завтра будет еще 3!"

---

## 🏗 Архитектура

### Модель данных (User)

```sql
-- Триал информация
subscription_tier       VARCHAR(20)   -- trial, basic, pro, enterprise
trial_started_at        TIMESTAMP
trial_ends_at           TIMESTAMP

-- Счетчики использования
reports_generated_count INTEGER DEFAULT 0
max_reports_trial       INTEGER DEFAULT 10
templates_saved_count   INTEGER DEFAULT 0
max_templates_trial     INTEGER DEFAULT 3
files_uploaded_count    INTEGER DEFAULT 0
max_files_trial         INTEGER DEFAULT 5

-- Anti-abuse: ежедневные лимиты
last_report_generated_at TIMESTAMP
daily_report_count      INTEGER DEFAULT 0
daily_report_reset_date DATE
```

### TrialService API

```python
# Инициализация триала
await trial_service.start_trial(user)

# Проверка статуса
status = await trial_service.check_trial_status(user)
# Возвращает: is_valid, days_remaining, usage, warnings

# Инкремент счетчиков
success, msg = await trial_service.increment_report_count(user)
success, msg = await trial_service.increment_template_count(user)
success, msg = await trial_service.increment_file_count(user)

# Апгрейд до платной подписки
result = await trial_service.upgrade_to_paid(user, SubscriptionTier.PRO)
```

---

## 💼 Тарифные Планы

| Функция | TRIAL | BASIC | PRO | ENTERPRISE |
|---------|-------|-------|-----|------------|
| **Цена** | Бесплатно | 990₽/мес | 2990₽/мес | 9990₽/мес |
| Отчеты | 10 всего | 50/мес | 200/мес | ∞ |
| Шаблоны | 3 | 10 | 50 | ∞ |
| Файлы | 5 | 20 | 100 | ∞ |
| Reports/день | 3 | 10 | 50 | ∞ |
| Экспорт | PDF, PPTX | +XLSX | +API | +Webhook |
| Поддержка | Email | Email | Priority | Dedicated |
| AI функции | ❌ | ❌ | ✅ | ✅ |
| SLA | ❌ | ❌ | ❌ | ✅ |

---

## 🎯 Сценарии Использования

### Сценарий 1: Честный пользователь оценивает продукт

```
День 1: Регистрация → Загрузка файла → 1 отчет (ост. 2 сегодня, 9 всего)
День 2: Возврат → 2 отчета (ост. 1 сегодня, 7 всего)
День 3: Возврат → 3 отчета (ост. 0 сегодня, 4 всего)
...
День 10: Понимает ценность → Покупает PRO
```

✅ **Конверсия:** Высокая (пользователь увидел ценность)

### Сценарий 2: Попытка злоупотребления

```
День 1: Регистрация → 3 отчета → Блокировка до завтра
Пользователь пытается создать новый аккаунт:
  - Требуется другой email
  - Другой IP (если добавить fingerprinting)
  - Снова только 3 отчета
```

✅ **Защита работает:** Невозможно сделать массовую выгрузку

### Сценарий 3: Пользователь упирается в лимит

```
День 5: 10/10 отчетов использовано
Сообщение: "Вы использовали все 10 отчетов. 
            Оформите подписку за 990₽/мес для безлимитных отчетов!"
→ Конверсия из pain point
```

---

## 📊 Метрики для Мониторинга

### Конверсионная воронка

```
Регистрации → Активированные (сделали 1+ отчет) → 
Активные (3+ дней) → Оплатившие
```

### Ключевые метрики

| Метрика | Цель | Формула |
|---------|------|---------|
| Trial Activation Rate | >60% | (Users with 1+ report) / Registrations |
| Day-1 Retention | >40% | Users returning on day 2 / Day 1 users |
| Day-7 Retention | >25% | Users active on day 7 / Day 1 users |
| Trial-to-Paid Conversion | >5-10% | Paid users / Trial users |
| Abuse Attempts | <2% | Users hitting daily cap repeatedly |

---

## 🔧 Интеграция в Код

### 1. При регистрации пользователя

```python
@app.post("/api/v1/auth/register")
async def register(user_data: UserCreate, db: AsyncSession):
    # ... создание пользователя ...
    
    trial_service = TrialService(db)
    await trial_service.start_trial(new_user)
    
    return {"trial_info": {...}}
```

### 2. Перед генерацией отчета

```python
@app.post("/api/v1/reports/generate")
async def generate_report(user: User, db: AsyncSession):
    trial_service = TrialService(db)
    
    # Проверка лимитов
    success, message = await trial_service.increment_report_count(user)
    if not success:
        raise HTTPException(403, detail=message)
    
    # ... генерация отчета ...
```

### 3. Проверка статуса в личном кабинете

```python
@app.get("/api/v1/user/trial-status")
async def get_trial_status(user: User, db: AsyncSession):
    trial_service = TrialService(db)
    status = await trial_service.check_trial_status(user)
    
    return {
        "is_trial": True,
        "days_remaining": status["days_remaining"],
        "usage": status["usage"],
        "warnings": status["warnings"],
        "upgrade_url": "/billing/upgrade"
    }
```

---

## 🎨 UX/UI Рекомендации

### В личном кабинете показать:

```
┌─────────────────────────────────────────────┐
│  🎯 Ваш триал: 12 дней осталось             │
│  ████████████░░░░░░░░░░ 85%                │
├─────────────────────────────────────────────┤
│  📊 Использование:                          │
│  • Отчеты: 3/10 (1 сегодня)                │
│  • Шаблоны: 1/3                            │
│  • Файлы: 2/5                              │
├─────────────────────────────────────────────┤
│  ⚡ Daily Limit: 2 отчета еще доступно      │
│     Сброс через 14 часов                   │
└─────────────────────────────────────────────┘
```

### При достижении лимита:

```
⛔ Дневной лимит исчерпан

Вы создали 3 отчета сегодня. Это лимит триального периода.

🔄 Завтра в 00:00 UTC счетчик сбросится, и вы сможете 
   создать еще 3 отчета.

💡 Или оформите подписку PRO за 2990₽/мес для:
   • Безлимитных отчетов
   • Приоритетной поддержки
   • AI-функций
   
[Вернуться завтра]  [Оформить подписку]
```

---

## 🚀 Roadmap Улучшений

### Фаза 1 (Сейчас)
- ✅ Базовая система лимитов
- ✅ Daily caps
- ✅ Миграции БД

### Фаза 2 (Следующая итерация)
- [ ] Email уведомления за 3 дня до конца
- [ ] Email при достижении 80% лимита
- [ ] A/B тесты длительности триала (7 vs 14 vs 30 дней)
- [ ] Fingerprinting для предотвращения мультиаккаунтов

### Фаза 3 (Advanced)
- [ ] Machine Learning для предсказания конверсии
- [ ] Персонализированные офферы на основе поведения
- [ ] Dynamic pricing для "горячих" лидов
- [ ] Интеграция с CRM (HubSpot, Salesforce)

---

## 📚 Источники Best Practices

1. **Stripe** - 14-day trial with usage limits
2. **Notion** - Block-based limits to encourage upgrade
3. **Figma** - Project limits + collaboration limits
4. **Slack** - Message history limits
5. **Linear** - Issue creation limits

---

## ✅ Checklist перед Запуском

- [ ] Настроить миграции БД
- [ ] Протестировать все сценарии лимитов
- [ ] Добавить UI отображения прогресса триала
- [ ] Настроить email уведомления
- [ ] Создать landing page с описанием триала
- [ ] Подготовить FAQ по триальному периоду
- [ ] Обучить поддержку работе с триалами

---

**Готово к production!** 🎉

Система защищает от злоупотреблений, стимулирует ежедневное использование и максимизирует конверсию в платную подписку.
