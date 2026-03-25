#!/bin/bash
# ==============================================================================
# PRODUCTION DEPLOYMENT SCRIPT
# Handles: Secrets generation, SSL setup, DB backups, Service start
# ==============================================================================

set -e

echo "🚀 Starting Production Deployment..."

# 1. Generate Secure Secrets if not exists
if [ ! -f .env ]; then
    echo "🔐 Generating secure secrets for .env..."
    cp .env.production.example .env
    
    # Generate random secrets
    SECRET_KEY=$(openssl rand -hex 32)
    JWT_SECRET=$(openssl rand -hex 32)
    DB_PASSWORD=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 20)
    
    # Replace placeholders
    sed -i "s/CHANGE_ME_TO_SECURE_RANDOM_STRING_64_CHARS_MIN/$SECRET_KEY/g" .env
    sed -i "s/SECURE_DB_PASSWORD_CHANGE_ME/$DB_PASSWORD/g" .env
    
    echo "✅ Secrets generated and saved to .env"
else
    echo "ℹ️  .env already exists, skipping generation."
fi

# 2. Setup SSL Certificates (Let's Encrypt)
setup_ssl() {
    DOMAIN=${1:-"yourdomain.com"}
    EMAIL=${2:-"admin@$DOMAIN"}
    
    echo "🔒 Setting up SSL for $DOMAIN..."
    
    # Check if certbot is installed
    if ! command -v certbot &> /dev/null; then
        echo "⚠️  Certbot not found. Installing..."
        apt-get update && apt-get install -y certbot python3-certbot-nginx
    fi
    
    # Request certificate (Standalone mode if nginx not running yet, or webroot if running)
    # For dockerized nginx, we usually use a shared volume approach
    mkdir -p ./ssl
    
    # Note: In production with Docker, you typically use a companion container like:
    # https://github.com/nginx-proxy/acme-companion
    # This script assumes manual initial setup or external cert management
    
    echo "⚠️  MANUAL STEP REQUIRED:"
    echo "   Run: sudo certbot certonly --standalone -d $DOMAIN -d www.$DOMAIN --email $EMAIL --agree-tos --non-interactive"
    echo "   Then copy certs to ./ssl/fullchain.pem and ./ssl/privkey.pem"
    
    if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
        sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem ./ssl/fullchain.pem
        sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem ./ssl/privkey.pem
        sudo chmod 600 ./ssl/privkey.pem
        echo "✅ SSL certificates copied to ./ssl/"
    else
        echo "❌ Certificates not found. Please run certbot manually first."
        exit 1
    fi
}

# 3. Setup Database Backups
setup_backups() {
    echo "💾 Setting up automated PostgreSQL backups..."
    
    BACKUP_DIR="./backups/postgres"
    mkdir -p $BACKUP_DIR
    
    # Create backup script
    cat > ./scripts/backup_db.sh << 'EOF'
#!/bin/bash
set -e
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="/app/backups/postgres/db_backup_$DATE.sql.gz"

# Load env vars
set -a
source /app/.env
set +a

echo "Starting backup to $BACKUP_PATH..."

# Extract DB credentials from DATABASE_URL
# Format: postgresql+asyncpg://user:pass@host:port/dbname
DB_USER=$(echo $DATABASE_URL | sed -n 's|.*://\([^:]*\):.*|\1|p')
DB_PASS=$(echo $DATABASE_URL | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
DB_HOST=$(echo $DATABASE_URL | sed -n 's|.*@\([^:]*\):.*|\1|p')
DB_NAME=$(echo $DATABASE_URL | sed -n 's|.*/\([^?]*).*|\1|p')

PGPASSWORD=$DB_PASS pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME | gzip > $BACKUP_PATH

echo "Backup completed: $BACKUP_PATH"

# Retention policy: Keep last 7 daily backups
find /app/backups/postgres -name "db_backup_*.sql.gz" -mtime +7 -delete
echo "Old backups cleaned up (retention: 7 days)"
EOF

    chmod +x ./scripts/backup_db.sh
    
    # Create cron job (requires host access or cron container)
    CRON_JOB="0 3 * * * cd /app && ./scripts/backup_db.sh >> /var/log/backup.log 2>&1"
    
    echo "✅ Backup script created at ./scripts/backup_db.sh"
    echo "ℹ️  To enable daily backups at 3 AM, add to crontab:"
    echo "   $CRON_JOB"
    
    # Optional: Add to system crontab if running as root on host
    if [ "$EUID" -eq 0 ]; then
        (crontab -l 2>/dev/null | grep -v "backup_db.sh"; echo "$CRON_JOB") | crontab -
        echo "✅ Cron job added successfully."
    fi
}

# 4. Start Services
start_services() {
    echo "🐳 Starting Docker containers..."
    
    # Ensure SSL dir exists
    mkdir -p ./ssl
    
    # Build and start
    docker-compose -f docker-compose.prod.yml up -d --build
    
    echo "✅ Services started!"
    echo "   - API: https://localhost:443"
    echo "   - DB: localhost:5432"
    echo "   - Redis: localhost:6379"
    echo "   - Prometheus: http://localhost:9090"
}

# Main execution
case "${1:-deploy}" in
    ssl)
        setup_ssl "$2" "$3"
        ;;
    backup)
        setup_backups
        ;;
    deploy)
        setup_backups
        # SSL setup requires domain argument
        if [ -n "$2" ]; then
            setup_ssl "$2" "$3"
        else
            echo "⚠️  Skipping SSL setup (no domain provided). Use: $0 deploy yourdomain.com"
        fi
        start_services
        ;;
    *)
        echo "Usage: $0 {deploy|ssl|backup} [domain] [email]"
        exit 1
        ;;
esac

echo "🎉 Deployment completed!"
