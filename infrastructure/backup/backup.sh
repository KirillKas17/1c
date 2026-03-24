#!/bin/bash
# Automated Backup Script for Dashboard Application
# Supports PostgreSQL, Redis, and file backups

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/backups}"
PG_HOST="${PG_HOST:-localhost}"
PG_PORT="${PG_PORT:-5432}"
PG_USER="${PG_USER:-postgres}"
PG_DB="${PG_DB:-1c_dashboard}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
APP_DATA_DIR="${APP_DATA_DIR:-/app/data}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
COMPRESSION="${COMPRESSION:-gzip}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Create backup directory
mkdir -p "$BACKUP_DIR"/{postgresql,redis,files}

TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# PostgreSQL Backup
backup_postgresql() {
    log_info "Starting PostgreSQL backup..."
    
    BACKUP_FILE="$BACKUP_DIR/postgresql/${PG_DB}_${TIMESTAMP}.sql"
    
    if command -v pg_dump &> /dev/null; then
        PGPASSWORD="${PG_PASSWORD:-}" pg_dump \
            -h "$PG_HOST" \
            -p "$PG_PORT" \
            -U "$PG_USER" \
            -d "$PG_DB" \
            -F c \
            -f "${BACKUP_FILE}.dump"
        
        if [ "$COMPRESSION" = "gzip" ]; then
            gzip "${BACKUP_FILE}.dump"
            log_info "PostgreSQL backup completed: ${BACKUP_FILE}.dump.gz"
        else
            log_info "PostgreSQL backup completed: ${BACKUP_FILE}.dump"
        fi
    else
        log_warn "pg_dump not found, skipping PostgreSQL backup"
    fi
}

# Redis Backup
backup_redis() {
    log_info "Starting Redis backup..."
    
    BACKUP_FILE="$BACKUP_DIR/redis/dump_${TIMESTAMP}.rdb"
    
    if command -v redis-cli &> /dev/null; then
        # Trigger BGSAVE
        redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" BGSAVE || true
        
        # Wait for save to complete
        sleep 5
        
        # Copy dump file if exists
        if [ -f "/var/lib/redis/dump.rdb" ]; then
            cp /var/lib/redis/dump.rdb "$BACKUP_FILE"
            
            if [ "$COMPRESSION" = "gzip" ]; then
                gzip "$BACKUP_FILE"
                log_info "Redis backup completed: ${BACKUP_FILE}.gz"
            else
                log_info "Redis backup completed: ${BACKUP_FILE}"
            fi
        else
            log_warn "Redis dump file not found"
        fi
    else
        log_warn "redis-cli not found, skipping Redis backup"
    fi
}

# Application Files Backup
backup_files() {
    log_info "Starting application files backup..."
    
    BACKUP_FILE="$BACKUP_DIR/files/app_data_${TIMESTAMP}.tar"
    
    if [ -d "$APP_DATA_DIR" ]; then
        tar -cf "$BACKUP_FILE" -C "$(dirname "$APP_DATA_DIR")" "$(basename "$APP_DATA_DIR")"
        
        if [ "$COMPRESSION" = "gzip" ]; then
            gzip "$BACKUP_FILE"
            log_info "Files backup completed: ${BACKUP_FILE}.gz"
        else
            log_info "Files backup completed: ${BACKUP_FILE}"
        fi
    else
        log_warn "Application data directory not found: $APP_DATA_DIR"
    fi
}

# Cleanup old backups
cleanup_old_backups() {
    log_info "Cleaning up backups older than $RETENTION_DAYS days..."
    
    find "$BACKUP_DIR/postgresql" -type f -mtime +$RETENTION_DAYS -delete
    find "$BACKUP_DIR/redis" -type f -mtime +$RETENTION_DAYS -delete
    find "$BACKUP_DIR/files" -type f -mtime +$RETENTION_DAYS -delete
    
    log_info "Cleanup completed"
}

# Verify backup integrity
verify_backup() {
    log_info "Verifying backup integrity..."
    
    # Check PostgreSQL backup
    PG_BACKUP=$(ls -t "$BACKUP_DIR/postgresql/"*.dump* 2>/dev/null | head -1)
    if [ -n "$PG_BACKUP" ]; then
        if [[ "$PG_BACKUP" == *.gz ]]; then
            gunzip -t "$PG_BACKUP" && log_info "PostgreSQL backup verified" || log_error "PostgreSQL backup corrupted"
        fi
    fi
    
    # Check Redis backup
    REDIS_BACKUP=$(ls -t "$BACKUP_DIR/redis/"*.rdb* 2>/dev/null | head -1)
    if [ -n "$REDIS_BACKUP" ]; then
        if [[ "$REDIS_BACKUP" == *.gz ]]; then
            gunzip -t "$REDIS_BACKUP" && log_info "Redis backup verified" || log_error "Redis backup corrupted"
        fi
    fi
    
    # Check files backup
    FILES_BACKUP=$(ls -t "$BACKUP_DIR/files/"*.tar* 2>/dev/null | head -1)
    if [ -n "$FILES_BACKUP" ]; then
        if [[ "$FILES_BACKUP" == *.gz ]]; then
            gunzip -t "$FILES_BACKUP" && log_info "Files backup verified" || log_error "Files backup corrupted"
        fi
    fi
}

# Upload to remote storage (S3 example)
upload_to_s3() {
    if [ -n "$AWS_BUCKET" ] && command -v aws &> /dev/null; then
        log_info "Uploading backups to S3 bucket: $AWS_BUCKET"
        
        aws s3 sync "$BACKUP_DIR" "s3://$AWS_BUCKET/backups/" \
            --exclude "*" \
            --include "*_${TIMESTAMP}*"
        
        log_info "S3 upload completed"
    else
        log_warn "S3 upload skipped (AWS_BUCKET not set or AWS CLI not installed)"
    fi
}

# Main execution
main() {
    log_info "=== Starting Backup Process ==="
    log_info "Timestamp: $TIMESTAMP"
    log_info "Backup Directory: $BACKUP_DIR"
    
    backup_postgresql
    backup_redis
    backup_files
    verify_backup
    cleanup_old_backups
    upload_to_s3
    
    log_info "=== Backup Process Completed ==="
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
