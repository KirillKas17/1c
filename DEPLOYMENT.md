# 🚀 PRODUCTION DEPLOYMENT GUIDE

## 1C Dashboard SaaS - Production Ready Checklist

Этот документ описывает шаги для развертывания приложения в production среде.

---

## 📋 ПРЕДВАРИТЕЛЬНЫЕ ТРЕБОВАНИЯ

- Сервер с Ubuntu 20.04+ или Debian 11+ (минимум 4 CPU, 8GB RAM, 50GB SSD)
- Доменное имя (например, `dashboard.yourcompany.ru`)
- Docker и Docker Compose v2.0+
- SSL сертификат (Let's Encrypt)

---

## 🔧 ШАГ 1: ПОДГОТОВКА СЕРВЕРА

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Проверка установки
docker --version
docker-compose --version
```

---

## 🔐 ШАГ 2: НАСТРОЙКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ

```bash
cd /path/to/project

# Копирование шаблона
cp .env.production.example .env

# Генерация секретов (автоматически при запуске deploy_prod.sh)
# Или вручную:
openssl rand -hex 32  # Для SECRET_KEY
openssl rand -hex 32  # Для JWT_SECRET_KEY
openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 20  # Для DB_PASSWORD
```

**Отредактируйте `.env` файл:**
- Замените все `CHANGE_ME_*` на реальные значения
- Настройте SMTP для email уведомлений
- Укажите правильный домен

---

## 🔒 ШАГ 3: ПОЛУЧЕНИЕ SSL СЕРТИФИКАТА

### Вариант A: Автоматически через скрипт

```bash
./scripts/deploy_prod.sh ssl yourdomain.com admin@yourdomain.com
```

### Вариант B: Вручную через Certbot

```bash
# Установка Certbot
sudo apt install certbot python3-certbot-nginx -y

# Получение сертификата
sudo certbot certonly --standalone \
  -d yourdomain.com \
  -d www.yourdomain.com \
  --email admin@yourdomain.com \
  --agree-tos \
  --non-interactive

# Копирование сертификатов
sudo mkdir -p ./ssl
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ./ssl/
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ./ssl/
sudo chmod 600 ./ssl/privkey.pem
```

---

## 💾 ШАГ 4: НАСТРОЙКА БЭКАПОВ

Скрипт бэкапа уже создан: `scripts/backup_db.sh`

### Автоматизация через Cron:

```bash
# Открыть crontab
crontab -e

# Добавить задачу (ежедневно в 3:00)
0 3 * * * cd /path/to/project && ./scripts/backup_db.sh >> /var/log/backup.log 2>&1
```

### Восстановление из бэкапа:

```bash
# Распаковать бэкап
gunzip db_backup_20240101_120000.sql.gz

# Восстановить базу
psql -h localhost -U dashboard_user -d dashboard_prod < db_backup_20240101_120000.sql
```

---

## 🚀 ШАГ 5: ЗАПУСК ПРОИЗВОДСТВЕННОЙ СРЕДЫ

```bash
# Полный деплой (генерация секретов + бэкапы + SSL + запуск)
sudo ./scripts/deploy_prod.sh deploy yourdomain.com admin@yourdomain.com

# Или только запуск сервисов
docker-compose -f docker-compose.prod.yml up -d --build
```

### Проверка статусa:

```bash
# Просмотр логов
docker-compose -f docker-compose.prod.yml logs -f api

# Проверка здоровья сервисов
docker-compose -f docker-compose.prod.yml ps

# Тест API
curl -k https://localhost/health
```

---

## 📊 ШАГ 6: МОНИТОРИНГ

### Prometheus (метрики):
- URL: `http://yourdomain.com:9090`
- Метрики API: `http://yourdomain.com/api/metrics`

### Grafana (дашборды):
- URL: `http://yourdomain.com:3000`
- Логин: `admin`
- Пароль: из `.env` (GRAFANA_ADMIN_PASSWORD)

**Рекомендуемые дашборды:**
1. FastAPI Metrics (ID: 12345)
2. PostgreSQL Database (ID: 9628)
3. Redis Cache (ID: 11835)
4. Nginx Web Server (ID: 12708)

---

## 🔍 ШАГ 7: ДИАГНОСТИКА И ЛОГИРОВАНИЕ

### Просмотр логов:

```bash
# API логи
docker-compose -f docker-compose.prod.yml logs -f api

# Nginx логи
docker-compose -f docker-compose.prod.yml logs -f nginx

# База данных
docker-compose -f docker-compose.prod.yml logs -f db

# Все логи вместе
docker-compose -f docker-compose.prod.yml logs -f
```

### Доступ в контейнеры:

```bash
# Войти в контейнер API
docker exec -it dashboard_api bash

# Посмотреть переменные окружения
docker exec dashboard_api env

# Проверить подключение к БД
docker exec -it dashboard_db psql -U dashboard_user -d dashboard_prod
```

---

## 🔄 ШАГ 8: ОБНОВЛЕНИЕ ПРИЛОЖЕНИЯ

```bash
# Остановка старых контейнеров
docker-compose -f docker-compose.prod.yml down

# Pull новых образов (если есть изменения)
docker-compose -f docker-compose.prod.yml pull

# Пересборка и запуск
docker-compose -f docker-compose.prod.yml up -d --build

# Проверка миграций
docker exec dashboard_api alembic current
```

---

## 🛡️ БЕЗОПАСНОСТЬ

### Рекомендации:

1. **Firewall (UFW):**
```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

2. **Fail2Ban:**
```bash
sudo apt install fail2ban -y
sudo systemctl enable fail2ban
```

3. **Regular Updates:**
```bash
# Еженедельное обновление
sudo apt update && sudo apt upgrade -y
```

4. **Backup Verification:**
- Проверяйте бэкапы еженедельно
- Тестируйте восстановление раз в месяц

---

## 📞 ПОДДЕРЖКА

При возникновении проблем:

1. Проверьте логи: `docker-compose logs -f`
2. Проверьте здоровье: `curl -k https://localhost/health`
3. Проверьте диски: `df -h`
4. Проверьте память: `free -h`
5. Проверьте CPU: `top`

---

## ✅ ЧЕК-ЛИСТ ГОТОВНОСТИ

- [ ] SSL сертификат установлен и обновляется автоматически
- [ ] Бэкапы настроены и тестируются регулярно
- [ ] Мониторинг (Prometheus + Grafana) работает
- [ ] Логи собираются и ротируются
- [ ] Firewall настроен
- [ ] Переменные окружения безопасны (нет дефолтных паролей)
- [ ] Health checks работают
- [ ] Документация обновлена

---

**Версия:** 1.0.0  
**Дата обновления:** 2024  
**Статус:** Production Ready ✅
