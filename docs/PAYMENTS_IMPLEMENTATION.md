# Интеграция платежной системы ЮKassa

## Обзор

Модуль платежей для интеграции с платежной системой ЮKassa, поддерживающий:
- Создание и обработку платежей
- Управление подписками (4 тарифа)
- Webhook уведомления
- Историю платежей

## Установка

1. Добавьте зависимости в `requirements.txt`:
```bash
requests>=2.31.0
```

2. Зарегистрируйтесь в [ЮKassa](https://yookassa.ru/) и получите:
   - `shopId` - ID магазина
   - `secretKey` - Секретный ключ для API

## Настройка

В конфигурации приложения (`config.py` или переменные окружения):

```python
YOOKASSA_SHOP_ID = 'ваш_shop_id'
YOOKASSA_SECRET_KEY = 'ваш_secret_key'
YOOKASSA_TEST_MODE = True  # True для тестового режима
```

Инициализация в приложении Flask:

```python
from src.payments.yookassa_service import init_payments

init_payments(app, db)
```

## Тарифы

| Тариф | Цена/мес | Лимит документов | Возможности |
|-------|----------|------------------|-------------|
| **Free** | 0 ₽ | 10 | Базовый анализ, Email поддержка |
| **Basic** | 990 ₽ | 100 | Расширенный анализ, Экспорт PDF, Приоритетная поддержка |
| **Pro** | 2 990 ₽ | 500 | Полный анализ, Экспорт PDF/PPTX, API доступ, История 1 год |
| **Enterprise** | 9 990 ₽ | Безлимит | Персональный менеджер, SLA 99.9%, Кастомизация |

## API Endpoints

### Публичные методы

#### `GET /payments/tariffs`
Получение списка тарифов

**Ответ:**
```json
{
  "tariffs": [
    {
      "tier": "free",
      "name": "Бесплатный",
      "price": 0,
      "documents_limit": 10,
      "features": ["Базовый анализ", "10 документов/мес", "Email поддержка"]
    },
    ...
  ]
}
```

#### `GET /payments/create/<tier>`
Создание платежа для выбранного тарифа (требуется аутентификация)

**Пример:**
```
GET /payments/create/pro
```

Перенаправляет на страницу оплаты ЮKassa.

#### `GET /payments/success`
Страница успешной оплаты

#### `POST /payments/webhook`
Webhook для уведомлений от ЮKassa

**Заголовки:**
- `X-Yookassa-Signature` - подпись уведомления

**Тело:** JSON от ЮKassa

### Методы пользователя (требуется авторизация)

#### `GET /payments/my-subscription`
Информация о текущей подписке

**Ответ:**
```json
{
  "id": 1,
  "user_id": 123,
  "tier": "pro",
  "start_date": "2024-01-01T00:00:00",
  "end_date": "2024-02-01T00:00:00",
  "is_active": true,
  "auto_renew": true
}
```

#### `GET /payments/history`
История платежей пользователя

**Ответ:**
```json
{
  "payments": [
    {
      "id": "uuid",
      "amount": 2990,
      "currency": "RUB",
      "status": "succeeded",
      "created_at": "2024-01-01T00:00:00"
    },
    ...
  ]
}
```

## Использование в коде

### Создание платежа (программно)

```python
from src.payments.yookassa_service import YooKassaPaymentService

service = YooKassaPaymentService(
    shop_id='your_shop_id',
    secret_key='your_secret_key',
    test_mode=True
)

# Создание платежа
payment_data, error = service.create_payment(
    amount=990.0,
    currency='RUB',
    description='Подписка Basic на 30 дней',
    user_id=123,
    subscription_tier='basic',
    return_url='https://yoursite.com/payment/success'
)

if error:
    print(f"Ошибка: {error}")
else:
    # Получаем URL для редиректа пользователя
    confirmation_url = service.get_confirmation_url(payment_data)
    print(f"Оплатить: {confirmation_url}")
```

### Проверка статуса платежа

```python
payment_info, error = service.get_payment_info('payment_id_from_yookassa')

if payment_info:
    print(f"Статус: {payment_info['status']}")
    print(f"Сумма: {payment_info['amount']['value']}")
```

### Отмена платежа

```python
success, error = service.cancel_payment('payment_id')

if success:
    print("Платеж отменен")
```

## Обработка webhook

ЮKassa отправляет уведомления о событиях:
- `payment.succeeded` - платеж успешен
- `payment.canceled` - платеж отменен
- `payment.waiting_for_capture` - ожидает подтверждения

Модуль автоматически:
1. Проверяет подпись уведомления
2. Обновляет статус платежа в БД
3. Активирует подписку при успешной оплате

## Модели данных

### Payment
```python
class Payment:
    id: str              # UUID
    user_id: int         # ID пользователя
    yookassa_payment_id: str  # ID в ЮKassa
    amount: float        # Сумма
    currency: str        # Валюта (RUB)
    status: enum         # pending/succeeded/canceled/failed
    description: str     # Описание
    payment_metadata: str     # JSON с доп. данными
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    is_test: bool
```

### Subscription
```python
class Subscription:
    id: int
    user_id: int
    tier: enum           # free/basic/pro/enterprise
    start_date: datetime
    end_date: datetime
    is_active: bool
    auto_renew: bool
    yookassa_subscription_id: str
```

## Тестирование

Запуск тестов:
```bash
python tests/test_payments.py
```

Тесты покрывают:
- ✅ Статусы платежей и тарифы
- ✅ Создание/отмена платежей
- ✅ Проверку подписи webhook
- ✅ Структуру тарифов
- ✅ Полный цикл оплаты

## Безопасность

1. **Проверка подписи**: Все webhook проверяются через HMAC-SHA256
2. **HTTPS**: Обязательно используйте HTTPS в продакшене
3. **Idempotency**: Каждый запрос имеет уникальный ключ идемпотентности
4. **Валидация**: Проверка всех входящих данных

## Режимы работы

### Тестовый режим
```python
YOOKASSA_TEST_MODE = True
```
- Использует тестовые ключи
- Платежи не списывают реальные деньги
- Рекомендуется для разработки

### Продакшен режим
```python
YOOKASSA_TEST_MODE = False
```
- Реальные платежи
- Требуется HTTPS
- Включите проверку подписи webhook

## Интеграция с фронтендом

### Пример кнопки оплаты (HTML)

```html
<!-- Карточка тарифа -->
<div class="tariff-card">
  <h3>Профессиональный</h3>
  <p class="price">2 990 ₽/мес</p>
  <ul>
    <li>500 документов/мес</li>
    <li>Экспорт PDF/PPTX</li>
    <li>API доступ</li>
  </ul>
  <a href="/payments/create/pro" class="btn-primary">
    Оформить подписку
  </a>
</div>
```

### Отображение статуса подписки

```javascript
// Получение информации о подписке
fetch('/payments/my-subscription')
  .then(r => r.json())
  .then(data => {
    if (data.is_active) {
      document.getElementById('tier').textContent = data.tier;
      document.getElementById('days-left').textContent = data.days_remaining;
    } else {
      showUpgradePrompt();
    }
  });
```

## Мониторинг

Отслеживайте метрики:
- Количество успешных платежей
- Конверсия в оплату
- Отток подписок
- Средний чек

## Поддержка

Документация ЮKassa: https://yookassa.ru/developers/api

При возникновении проблем:
1. Проверьте логи приложения
2. Убедитесь в правильности ключей API
3. Проверьте статус в личном кабинете ЮKassa

## Changelog

### v1.0.0
- ✅ Начальная реализация
- ✅ 4 тарифа
- ✅ Webhook уведомления
- ✅ История платежей
- ✅ Тесты (16 тестов, 100% pass)
