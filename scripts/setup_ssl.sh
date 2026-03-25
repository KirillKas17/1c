#!/bin/bash
# SSL Certificate Setup Script
# Автоматическая настройка SSL сертификатов для 1C Dashboard Service

set -e

echo "🔐 SSL Certificate Setup for 1C Dashboard Service"
echo "=================================================="

CERT_DIR="/workspace/ssl"
mkdir -p "$CERT_DIR"

# Проверка: используем ли мы Let's Encrypt или самоподписанные сертификаты
if [ "$USE_LETS_ENCRYPT" = "true" ]; then
    echo "🌟 Настройка Let's Encrypt..."
    
    if [ -z "$DOMAIN_NAME" ]; then
        echo "❌ Ошибка: DOMAIN_NAME не установлен для Let's Encrypt"
        exit 1
    fi
    
    # Установка Certbot
    apt-get update -qq
    apt-get install -y -qq certbot
    
    # Получение сертификата
    certbot certonly --standalone -d "$DOMAIN_NAME" \
        --email "$ADMIN_EMAIL" \
        --agree-tos \
        --non-interactive || {
        echo "⚠️ Не удалось получить сертификат Let's Encrypt"
        echo "Проверьте, что домен указывает на этот сервер и порт 80 открыт"
        exit 1
    }
    
    # Копирование сертификатов
    cp "/etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem" "$CERT_DIR/cert.pem"
    cp "/etc/letsencrypt/live/$DOMAIN_NAME/privkey.pem" "$CERT_DIR/key.pem"
    
    echo "✅ Let's Encrypt сертификаты успешно получены!"
    
else
    echo "📝 Генерация самоподписанных сертификатов (для тестирования)..."
    
    # Генерация самоподписанного сертификата
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$CERT_DIR/key.pem" \
        -out "$CERT_DIR/cert.pem" \
        -subj "/C=RU/ST=Moscow/L=Moscow/O=1C Dashboard/CN=localhost" \
        -addext "subjectAltName=DNS:localhost,DNS:*.localhost,IP:127.0.0.1"
    
    echo "✅ Самоподписанные сертификаты сгенерированы!"
    echo "⚠️ Внимание: Браузеры будут показывать предупреждение для самоподписанных сертификатов"
fi

# Установка правильных прав
chmod 600 "$CERT_DIR/key.pem"
chmod 644 "$CERT_DIR/cert.pem"

echo ""
echo "📁 Сертификаты сохранены в: $CERT_DIR"
echo "   - cert.pem (публичный сертификат)"
echo "   - key.pem (приватный ключ)"
echo ""

# Создание конфигурации для Nginx (если используется)
if [ -f "/etc/nginx/nginx.conf" ]; then
    echo "🔄 Обновление конфигурации Nginx..."
    
    cat > /etc/nginx/conf.d/ssl.conf << NGINX_EOF
ssl_protocols TLSv1.2 TLSv1.3;
ssl_prefer_server_ciphers on;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 10m;
NGINX_EOF
    
    echo "✅ Конфигурация Nginx обновлена!"
fi

echo ""
echo "🎉 SSL настройка завершена!"
echo ""
echo "Следующие шаги:"
echo "1. Для production: замените самоподписанные сертификаты на настоящие от Let's Encrypt"
echo "2. Настройте Docker Compose для использования SSL (см. docker-compose.prod.yml)"
echo "3. Перезапустите сервис: docker-compose restart"
echo ""
echo "Для автоматического обновления Let's Encrypt добавьте в crontab:"
echo "0 0 1 * * certbot renew --quiet"
