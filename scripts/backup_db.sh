#!/bin/bash
# Automated Database Backup Script for PostgreSQL
# Runs daily, keeps 7 days retention, compresses backups

set -e

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"
BACKUP_PATH="$BACKUP_DIR/db_backup_$DATE.sql.gz"
RETENTION_DAYS=7

echo "🗄️  Starting PostgreSQL backup at $(date)"
echo "Backup path: $BACKUP_PATH"

# Load environment variables from .env file
if [ -f "/.env" ]; then
    set -a
    source /.env
    set +a
fi

# Extract database credentials from DATABASE_URL
# Format: postgresql+asyncpg://user:pass@host:port/dbname
extract_db_param() {
    local url="$1"
    local param="$2"
    
    case $param in
        user)
            echo "$url" | sed -n 's|.*://\([^:]*\):.*|\1|p'
            ;;
        password)
            echo "$url" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p'
            ;;
        host)
            echo "$url" | sed -n 's|.*@\([^:]*\):.*|\1|p'
            ;;
        port)
            echo "$url" | sed -n 's|.*@[^:]*:\([0-9]*\)/.*|\1|p'
            ;;
        dbname)
            echo "$url" | sed -n 's|.*/\([^?]*).*|\1|p'
            ;;
    esac
}

DB_USER=$(extract_db_param "$DATABASE_URL" "user")
DB_PASS=$(extract_db_param "$DATABASE_URL" "password")
DB_HOST=$(extract_db_param "$DATABASE_URL" "host")
DB_NAME=$(extract_db_param "$DATABASE_URL" "dbname")

# Validate credentials
if [ -z "$DB_USER" ] || [ -z "$DB_PASS" ] || [ -z "$DB_HOST" ] || [ -z "$DB_NAME" ]; then
    echo "❌ Error: Could not extract database credentials from DATABASE_URL"
    echo "DATABASE_URL: $DATABASE_URL"
    exit 1
fi

echo "Connecting to DB: $DB_NAME@$DB_HOST as $DB_USER"

# Create backup directory if not exists
mkdir -p "$BACKUP_DIR"

# Perform backup with pg_dump and compress with gzip
PGPASSWORD="$DB_PASS" pg_dump \
    -h "$DB_HOST" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --format=plain \
    --no-owner \
    --no-privileges \
    | gzip > "$BACKUP_PATH"

# Verify backup was created
if [ -f "$BACKUP_PATH" ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_PATH" | cut -f1)
    echo "✅ Backup completed successfully!"
    echo "   File: $(basename $BACKUP_PATH)"
    echo "   Size: $BACKUP_SIZE"
else
    echo "❌ Backup failed: File not created"
    exit 1
fi

# Cleanup old backups (retention policy)
echo "🧹 Cleaning up backups older than $RETENTION_DAYS days..."
DELETED_COUNT=$(find "$BACKUP_DIR" -name "db_backup_*.sql.gz" -type f -mtime +$RETENTION_DAYS -delete -print | wc -l)

if [ "$DELETED_COUNT" -gt 0 ]; then
    echo "   Deleted $DELETED_COUNT old backup(s)"
else
    echo "   No old backups to delete"
fi

# List current backups
echo ""
echo "📦 Current backups:"
ls -lh "$BACKUP_DIR"/db_backup_*.sql.gz 2>/dev/null || echo "   No backups found"

echo ""
echo "🎉 Backup process finished at $(date)"
