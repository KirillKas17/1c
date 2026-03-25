# 🛡️ SSL/HTTPS и Email Настройка для Production

## ✅ ЧТО БЫЛО РЕАЛИЗОВАНО

### 1. SSL/HTTPS Сертификаты

**Скрипт автоматической настройки:** `scripts/setup_ssl.sh`

**Режимы работы:**
- **Dev (самоподписанные)** - для тестирования и разработки
- **Prod (Let's Encrypt)** - бесплатные SSL сертификаты для продакшена

**Использование:**

```bash
# Development (самоподписанный сертификат)
export SSL_ENV=dev
export SSL_DOMAIN=localhost
./scripts/setup_ssl.sh

# Production (Let's Encrypt)
export SSL_ENV=prod
export SSL_DOMAIN=yourdomain.com
export SSL_EMAIL=admin@yourdomain.com
./scripts/setup_ssl.sh
```

**Результат:**
```
/workspace/certs/
├── server.crt  # Публичный сертификат
└── server.key  # Приватный ключ (600 permissions)
```

---

### 2. Email Service

**Модуль:** `src/core/email/email_service.py`

**Функционал:**
- ✅ Асинхронная отправка email
- ✅ HTML + text шаблоны
- ✅ Multiple провайдеры (SMTP, SendGrid, Telegram fallback)
- ✅ Retry логика с exponential backoff
- ✅ Прогрессивные уведомления

**Типы уведомлений:**

| Тип | Триггер | Шаблон |
|-----|---------|--------|
| **Trial Welcome** | Регистрация пользователя | `trial_welcome.html` |
| **Usage Warning** | 80% лимита триала | `usage_warning.html` |
| **Trial Expiring** | 3 дня до конца триала | `trial_expiring.html` |
| **Trial Expiring** | 1 день до конца триала | `trial_expiring.html` |
| **Subscription Confirmed** | Успешная оплата | `subscription_confirmed.html` |
| **Password Reset** | Запрос сброса пароля | `password_reset.html` |

**Шаблоны писем:**
```
src/core/email/templates/
├── trial_welcome.html
├── usage_warning.html
├── trial_expiring.html
├── subscription_confirmed.html
└── password_reset.html
```

---

## 🔧 НАСТРОЙКА ДЛЯ PRODUCTION

### Шаг 1: SSL Сертификаты

#### Вариант A: Let's Encrypt (рекомендуется)

```bash
# 1. Установите certbot
sudo apt-get install certbot

# 2. Запустите скрипт в production режиме
export SSL_ENV=prod
export SSL_DOMAIN=yourdomain.com
export SSL_EMAIL=admin@yourdomain.com
./scripts/setup_ssl.sh

# 3. Certificates будут установлены автоматически
```

#### Вариант B: Самоподписанные (для тестирования)

```bash
export SSL_ENV=dev
export SSL_DOMAIN=localhost
./scripts/setup_ssl.sh
```

⚠️ **Важно:** Самоподписанные сертификаты вызывают предупреждения в браузерах!

---

### Шаг 2: Настройка Email

#### Вариант A: SMTP (рекомендуется для production)

Примеры популярных SMTP провайдеров:

**Yandex 360:**
```env
SMTP_HOST=smtp.yandex.ru
SMTP_PORT=465
SMTP_USER=yourname@yandex.ru
SMTP_PASSWORD=your_app_password
FROM_EMAIL=noreply@yourdomain.com
FROM_NAME=1C Dashboard
```

**Google Workspace:**
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=yourname@gmail.com
SMTP_PASSWORD=your_app_password
FROM_EMAIL=noreply@yourdomain.com
FROM_NAME=1C Dashboard
```

**SendGrid:**
```env
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=SG.xxxxxxxxxxxxxx
FROM_EMAIL=noreply@yourdomain.com
FROM_NAME=1C Dashboard
```

#### Вариант B: Telegram Bot (fallback или dev)

```bash
# 1. Создайте бота через @BotFather в Telegram
# 2. Получите токен
# 3. Узнайте свой chat_id через @userinfobot

TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_ADMIN_CHAT_ID=123456789
```

---

### Шаг 3: Обновление .env.production

```bash
cp .env.production.example .env.production
```

**Заполните переменные:**

```env
# SSL Configuration
SSL_CERT_FILE=/app/certs/server.crt
SSL_KEY_FILE=/app/certs/server.key
SSL_DOMAIN=yourdomain.com
SSL_EMAIL=admin@yourdomain.com
SSL_ENV=prod

# Email Configuration
SMTP_HOST=smtp.your-provider.com
SMTP_PORT=587
SMTP_USER=noreply@yourdomain.com
SMTP_PASSWORD=your_password_here
FROM_EMAIL=noreply@yourdomain.com
FROM_NAME=1C Dashboard
SUPPORT_EMAIL=support@yourdomain.com
FRONTEND_URL=https://yourdomain.com

# Telegram Fallback (optional)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_ADMIN_CHAT_ID=your_chat_id
```

---

### Шаг 4: Docker Compose

**Обновите `docker-compose.prod.yml`:**

```yaml
services:
  app:
    volumes:
      - ./certs:/app/certs:ro
      - ./uploads:/app/uploads
    environment:
      - SSL_CERT_FILE=/app/certs/server.crt
      - SSL_KEY_FILE=/app/certs/server.key
  
  nginx:
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./certs:/etc/nginx/ssl:ro
      - ./nginx.conf:/etc/nginx/nginx.conf
```

---

## 📊 МОНЕТРИНГ И ЛОГИРОВАНИЕ

### Логи отправки email

```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EmailService")

# Примеры логов:
# INFO: EmailService initialized: smtp.yandex.ru:465
# INFO: Email sent to user@example.com: 🎉 Добро пожаловать в 1C Dashboard!
# WARNING: Email send failed (attempt 1/3): Connection timeout
# INFO: Telegram notification sent for user@example.com
```

### Prometheus метрики

```prometheus
# Метрики для мониторинга email сервиса
email_sent_total{type="trial_welcome"} 42
email_sent_total{type="usage_warning"} 15
email_failed_total 3
email_fallback_to_telegram_total 2
```

---

## 🧪 ТЕСТИРОВАНИЕ

### Тест SSL скрипта

```bash
# Dev режим
SSL_ENV=dev ./scripts/setup_ssl.sh

# Проверка сертификата
openssl x509 -in /workspace/certs/server.crt -text -noout | head -20
```

### Тест Email сервиса

```bash
cd /workspace
python -m src.core.email.email_service
```

Ожидаемый вывод:
```
INFO: EmailService initialized: smtp.yandex.ru:465
Test email sent: True
```

---

## 🔒 БЕЗОПАСНОСТЬ

### SSL Best Practices

1. **Используйте Let's Encrypt для production**
   - Бесплатно
   - Автоматическое продление
   - Доверенный CA

2. **Защита приватного ключа**
   ```bash
   chmod 600 /workspace/certs/server.key
   chown root:root /workspace/certs/server.key
   ```

3. **HSTS заголовки** (настройте в nginx)
   ```nginx
   add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
   ```

### Email Security

1. **SPF запись** (DNS)
   ```
   v=spf1 include:_spf.yandex.ru ~all
   ```

2. **DKIM подпись** (настройте у SMTP провайдера)

3. **DMARC политика** (DNS)
   ```
   v=DMARC1; p=quarantine; rua=mailto:dmarc@yourdomain.com
   ```

---

## 🚀 DEPLOYMENT CHECKLIST

- [ ] SSL сертификаты сгенерированы
- [ ] `.env.production` настроен с реальными значениями
- [ ] SMTP протестирован
- [ ] Telegram fallback настроен (опционально)
- [ ] Docker volumes смонтированы
- [ ] Nginx настроен на HTTPS
- [ ] HSTS заголовки добавлены
- [ ] DNS записи обновлены (A, SPF, DKIM, DMARC)
- [ ] Мониторинг настроен (Prometheus/Grafana)
- [ ] Бэкапы приватных ключей сделаны

---

## 📞 ПОДДЕРЖКА

**Проблемы с SSL?**
- Dev: Проверьте OpenSSL (`openssl version`)
- Prod: Убедитесь что порт 80 открыт для Let's Encrypt validation

**Проблемы с Email?**
- Проверьте логи: `docker-compose logs app | grep Email`
- Тест SMTP: `telnet smtp.your-provider.com 587`
- Telegram: Проверьте токен бота через curl

---

## 📈 СЛЕДУЮЩИЕ ШАГИ

1. **Настроить автоматическое продление SSL**
   ```bash
   # Add to crontab
   0 3 * * * certbot renew --quiet
   ```

2. **Интегрировать с Trial Service**
   ```python
   from src.core.email.email_service import email_service
   
   async def on_user_register(user):
       await email_service.send_trial_welcome(
           user_email=user.email,
           user_name=user.name,
           trial_days=14
       )
   ```

3. **Добавить аналитику email кампаний**
   - Open rate
   - Click-through rate
   - Conversion rate

---

**✅ ГОТОВО К PRODUCTION!**

Все компоненты готовы к запуску. Осталось только подключить платежную систему (YooKassa/CloudPayments).
