#!/bin/bash
# Production Deployment Script for 1C Dashboard Service
# Автоматическое развертывание на Ubuntu VPS

set -e

echo "🚀 Starting deployment of 1C Dashboard Service..."

# Configuration
APP_NAME="1c-dashboard"
APP_DIR="/opt/$APP_NAME"
PYTHON_VERSION="3.11"
DOMAIN="${DOMAIN:-dashboard.example.com}"
EMAIL="${EMAIL:-admin@example.com}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_error "Please run as root (sudo ./deploy.sh)"
    exit 1
fi

# Step 1: Install system dependencies
log_info "Installing system dependencies..."
apt-get update
apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    nginx \
    certbot \
    python3-certbot-nginx \
    redis-server \
    postgresql \
    postgresql-contrib \
    docker.io \
    docker-compose \
    git \
    curl \
    wget

# Step 2: Create application directory
log_info "Creating application directory..."
mkdir -p $APP_DIR
cd $APP_DIR

# Step 3: Clone or update repository
if [ -d ".git" ]; then
    log_info "Updating repository..."
    git pull origin main
else
    log_info "Cloning repository..."
    git clone https://github.com/KirillKas17/1c.git .
fi

# Step 4: Setup Python virtual environment
log_info "Setting up Python virtual environment..."
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -e .

# Step 5: Setup PostgreSQL
log_info "Configuring PostgreSQL..."
sudo -u postgres psql -c "CREATE DATABASE ${APP_NAME}_db;" || true
sudo -u postgres psql -c "CREATE USER ${APP_NAME}_user WITH PASSWORD '${DB_PASSWORD:-secure_password}';" || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${APP_NAME}_db TO ${APP_NAME}_user;" || true

# Step 6: Create .env file
log_info "Creating .env configuration..."
cat > .env << EOF
APP_NAME=$APP_NAME
ENVIRONMENT=production
SECRET_KEY=${SECRET_KEY:-$(openssl rand -hex 32)}
DATABASE_URL=postgresql://${APP_NAME}_user:${DB_PASSWORD:-secure_password}@localhost/${APP_NAME}_db
REDIS_URL=redis://localhost:6379/0
DOMAIN=$DOMAIN
ALLOWED_HOSTS=$DOMAIN,localhost,127.0.0.1
JWT_SECRET_KEY=${JWT_SECRET:-$(openssl rand -hex 32)}
LOG_LEVEL=INFO
MAX_FILE_SIZE_MB=100
EOF

# Step 7: Run database migrations
log_info "Running database migrations..."
alembic upgrade head || log_warn "Database migrations skipped (if not configured)"

# Step 8: Setup systemd service
log_info "Creating systemd service..."
cat > /etc/systemd/system/$APP_NAME.service << EOF
[Unit]
Description=1C Dashboard Service
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/streamlit run src/app.py --server.port 8501 --server.address 0.0.0.0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable $APP_NAME
systemctl restart $APP_NAME

# Step 9: Configure Nginx
log_info "Configuring Nginx..."
cat > /etc/nginx/sites-available/$APP_NAME << EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://localhost:8501;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket support for Streamlit
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Increase timeouts for long-running operations
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    # Static files
    location /static {
        alias $APP_DIR/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
EOF

ln -sf /etc/nginx/sites-available/$APP_NAME /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx

# Step 10: Setup SSL with Let's Encrypt
if [ "$DOMAIN" != "localhost" ] && [ "$DOMAIN" != "127.0.0.1" ]; then
    log_info "Setting up SSL certificate with Let's Encrypt..."
    certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email $EMAIL
    
    # Auto-renewal setup
    certbot renew --dry-run
fi

# Step 11: Start and enable services
log_info "Starting services..."
systemctl enable redis-server
systemctl start redis-server
systemctl enable postgresql
systemctl start postgresql
systemctl enable $APP_NAME
systemctl start $APP_NAME
systemctl enable nginx
systemctl start nginx

# Step 12: Health check
log_info "Running health check..."
sleep 5
if curl -f http://localhost:8501 > /dev/null 2>&1; then
    log_info "✅ Application is running successfully!"
else
    log_error "❌ Application failed to start. Check logs: journalctl -u $APP_NAME"
    exit 1
fi

# Summary
echo ""
echo "=========================================="
echo "✅ Deployment completed successfully!"
echo "=========================================="
echo ""
echo "📍 Application URL: http$([ -f /etc/letsencrypt/live/$DOMAIN/fullchain.pem ] && echo "s" || echo "")://$DOMAIN"
echo "📍 App Directory: $APP_DIR"
echo "📍 Logs: journalctl -u $APP_NAME -f"
echo ""
echo "Useful commands:"
echo "  - Restart app: systemctl restart $APP_NAME"
echo "  - View logs: journalctl -u $APP_NAME -f"
echo "  - Stop app: systemctl stop $APP_NAME"
echo "  - Update: cd $APP_DIR && git pull && systemctl restart $APP_NAME"
echo ""
