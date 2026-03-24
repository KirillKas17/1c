# HTTPS Configuration Guide

## Overview
This guide explains how to enable HTTPS for the application using SSL/TLS certificates.

## Production SSL Setup

### Option 1: Let's Encrypt (Recommended - Free)

#### Prerequisites
- Domain name pointing to your server
- Server with ports 80 and 443 open
- `certbot` installed

#### Installation

```bash
# Install certbot
sudo apt-get update
sudo apt-get install certbot python3-certbot-nginx

# Obtain certificate (replace with your domain)
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renewal is set up automatically
# Test renewal:
sudo certbot renew --dry-run
```

#### Nginx Configuration

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;
    
    # SSL Certificate
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    # SSL Configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;
    
    # Security Headers
    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # Application configuration
    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Option 2: Self-Signed Certificate (Development Only)

```bash
# Generate self-signed certificate
mkdir -p /workspace/infrastructure/ssl
cd /workspace/infrastructure/ssl

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout app.key \
  -out app.crt \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"

# Generate DH parameters for enhanced security (optional, takes time)
openssl dhparam -out dhparam.pem 2048
```

### Option 3: Commercial SSL Certificate

Purchase from providers like:
- DigiCert
- Comodo
- GlobalSign
- GoDaddy

Follow provider's instructions for certificate installation.

## Docker Compose SSL Setup

Update `docker-compose.yml`:

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "443:443"
    volumes:
      - ./infrastructure/ssl:/etc/ssl/app:ro
    environment:
      - SSL_CERTIFICATE=/etc/ssl/app/app.crt
      - SSL_KEY=/etc/ssl/app/app.key
      - SECRET_KEY=${SECRET_KEY}
    restart: unless-stopped
  
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./infrastructure/nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./infrastructure/ssl:/etc/ssl/app:ro
    depends_on:
      - app
    restart: unless-stopped
```

## Environment Variables

Create `.env` file:

```bash
# Security
SECRET_KEY=your-super-secret-key-min-32-chars
ACCESS_TOKEN_MINUTES=15
REFRESH_TOKEN_DAYS=7

# SSL (production)
SSL_MODE=production
SSL_CERTIFICATE=/path/to/certificate.crt
SSL_KEY=/path/to/private.key

# HTTPS Settings
HTTPS_ENABLED=true
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=Lax
```

## Flask App HTTPS Configuration

Update your Flask app (`app.py` or `main.py`):

```python
from flask import Flask
import os

app = Flask(__name__)

# Security configurations
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SESSION_COOKIE_SECURE'] = os.getenv('HTTPS_ENABLED', 'false').lower() == 'true'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(minutes=30)

# Force HTTPS in production
@app.before_request
def force_https():
    if os.getenv('HTTPS_ENABLED', 'false').lower() == 'true':
        if not request.is_secure and not app.debug:
            return redirect(request.url.replace('http://', 'https://'), code=301)

if __name__ == '__main__':
    if os.getenv('HTTPS_ENABLED', 'false').lower() == 'true':
        # Production with SSL
        app.run(
            host='0.0.0.0',
            port=443,
            ssl_context=(
                os.getenv('SSL_CERTIFICATE'),
                os.getenv('SSL_KEY')
            )
        )
    else:
        # Development without SSL
        app.run(host='0.0.0.0', port=5000, debug=True)
```

## Security Headers Middleware

Add to your Flask app:

```python
@app.after_request
def add_security_headers(response):
    response.headers['Strict-Transport-Security'] = 'max-age=63072000; includeSubDomains'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' cdn.tailwindcss.com"
    return response
```

## Testing HTTPS

```bash
# Test SSL configuration
curl -I https://yourdomain.com

# Check SSL Labs rating
# Visit: https://www.ssllabs.com/ssltest/

# Test certificate
openssl s_client -connect yourdomain.com:443 -servername yourdomain.com

# Verify redirect from HTTP to HTTPS
curl -I http://yourdomain.com
# Should return 301 redirect to HTTPS
```

## Certificate Renewal (Let's Encrypt)

Automatic renewal is configured by certbot. Verify with:

```bash
# Check renewal schedule
sudo systemctl list-timers | grep certbot

# Manual renewal test
sudo certbot renew --dry-run

# Force renewal
sudo certbot renew --force-renewal

# Reload nginx after renewal
sudo systemctl reload nginx
```

## Troubleshooting

### Common Issues

1. **Mixed Content Warnings**
   - Ensure all resources (CSS, JS, images) use HTTPS or protocol-relative URLs
   - Check browser console for mixed content errors

2. **Certificate Errors**
   - Verify certificate is not expired
   - Check domain name matches certificate
   - Ensure certificate chain is complete

3. **Redirect Loops**
   - Check reverse proxy headers (X-Forwarded-Proto)
   - Verify Flask trust_proxy setting

```python
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1)
```

## Compliance Notes (152-ФЗ Russia)

For Russian data protection compliance:

1. Store personal data of Russian citizens on servers in Russia
2. Implement proper access controls and audit logging
3. Encrypt data in transit (HTTPS) and at rest
4. Maintain data processing records
5. Implement user consent mechanisms
6. Provide data export/deletion capabilities

See `docs/COMPLIANCE_152FZ.md` for detailed requirements.
