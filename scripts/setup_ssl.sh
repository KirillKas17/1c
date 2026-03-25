#!/bin/bash
# 🛡️ SSL/HTTPS Certificate Setup Script for 1C Dashboard Service
# Supports: Self-signed (dev) + Let's Encrypt (prod)

set -e

CERT_DIR="/workspace/certs"
DOMAIN="${SSL_DOMAIN:-localhost}"
EMAIL="${SSL_EMAIL:-admin@localhost}"
ENV_TYPE="${SSL_ENV:-dev}" # dev or prod

echo "🔐 SSL Setup Script Started"
echo "   Domain: $DOMAIN"
echo "   Email: $EMAIL"
echo "   Environment: $ENV_TYPE"
echo ""

# Create certs directory
mkdir -p "$CERT_DIR"
chmod 700 "$CERT_DIR"

if [ "$ENV_TYPE" = "dev" ]; then
    echo "📝 Generating self-signed certificate for development..."
    
    # Generate private key
    openssl genrsa -out "$CERT_DIR/server.key" 2048
    chmod 600 "$CERT_DIR/server.key"
    
    # Generate self-signed certificate
    openssl req -new -x509 \
        -key "$CERT_DIR/server.key" \
        -out "$CERT_DIR/server.crt" \
        -days 365 \
        -subj "/C=RU/ST=Moscow/L=Moscow/O=1C Dashboard/CN=$DOMAIN" \
        -addext "subjectAltName=DNS:$DOMAIN,DNS:localhost,IP:127.0.0.1"
    
    echo "✅ Self-signed certificate generated successfully!"
    echo ""
    echo "📁 Certificate files:"
    echo "   Key:  $CERT_DIR/server.key"
    echo "   Cert: $CERT_DIR/server.crt"
    echo ""
    echo "⚠️  BROWSER WARNING:"
    echo "   Self-signed certificates will show security warnings in browsers."
    echo "   This is NORMAL for development. Click 'Advanced' → 'Proceed' to continue."
    echo ""
    echo "🔧 To trust this certificate system-wide (optional):"
    echo "   sudo cp $CERT_DIR/server.crt /usr/local/share/ca-certificates/"
    echo "   sudo update-ca-certificates"
    
elif [ "$ENV_TYPE" = "prod" ]; then
    echo "🌐 Production mode detected"
    echo ""
    
    if command -v certbot &> /dev/null; then
        echo "✅ Certbot found. Proceeding with Let's Encrypt..."
        
        # Stop nginx temporarily if running
        if systemctl is-active --quiet nginx; then
            echo "⏸️  Stopping nginx temporarily..."
            sudo systemctl stop nginx
        fi
        
        # Get certificate from Let's Encrypt
        sudo certbot certonly \
            --standalone \
            --preferred-challenges http \
            --email "$EMAIL" \
            --agree-tos \
            --non-interactive \
            --domain "$DOMAIN"
        
        # Copy certificates to our directory
        sudo cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$CERT_DIR/server.crt"
        sudo cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" "$CERT_DIR/server.key"
        sudo chmod 600 "$CERT_DIR/server.key"
        
        # Restart nginx
        if systemctl is-active --quiet nginx; then
            echo "▶️  Starting nginx..."
            sudo systemctl start nginx
        fi
        
        echo ""
        echo "✅ Let's Encrypt certificate installed successfully!"
        echo ""
        echo "📁 Certificate files:"
        echo "   Key:  $CERT_DIR/server.key"
        echo "   Cert: $CERT_DIR/server.crt"
        echo ""
        echo "🔄 Auto-renewal is handled by certbot automatically."
        echo "   Test renewal with: sudo certbot renew --dry-run"
        
    else
        echo "❌ Certbot not found!"
        echo ""
        echo "Please install certbot first:"
        echo "   Ubuntu/Debian: sudo apt-get install certbot"
        echo "   CentOS/RHEL:   sudo yum install certbot"
        echo "   Docker:        Use certbot-docker image"
        echo ""
        echo "Or switch to dev mode: export SSL_ENV=dev"
        exit 1
    fi
else
    echo "❌ Invalid environment type: $ENV_TYPE"
    echo "   Use 'dev' or 'prod'"
    exit 1
fi

echo ""
echo "📋 NEXT STEPS:"
echo "1. Update docker-compose.yml to mount certificates:"
echo "   volumes:"
echo "     - ./certs:/app/certs:ro"
echo ""
echo "2. Set environment variables in .env.production:"
echo "   SSL_CERT_FILE=/app/certs/server.crt"
echo "   SSL_KEY_FILE=/app/certs/server.key"
echo ""
echo "3. Restart the application:"
echo "   docker-compose restart"
echo ""
echo "🎉 SSL Setup Complete!"
