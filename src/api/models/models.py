"""
Database models for 1C Dashboard Service.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Text, JSON, Enum as SQLEnum, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

from src.api.db.database import Base


class SubscriptionTier(enum.Enum):
    FREE = "free"
    TRIAL = "trial"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class User(Base):
    """User model with advanced trial and subscription management."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    company_name = Column(String(255), nullable=True)  # For B2B
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Subscription info
    subscription_tier = Column(SQLEnum(SubscriptionTier), default=SubscriptionTier.TRIAL)
    subscription_expires_at = Column(DateTime(timezone=True), nullable=True)
    trial_started_at = Column(DateTime(timezone=True), nullable=True)
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)  # Explicit end date
    
    # Usage tracking for trial limits (anti-abuse)
    reports_generated_count = Column(Integer, default=0)  # Total reports in trial
    max_reports_trial = Column(Integer, default=10)       # Limit: 10 reports max
    templates_saved_count = Column(Integer, default=0)    # Saved templates
    max_templates_trial = Column(Integer, default=3)      # Limit: 3 templates max
    files_uploaded_count = Column(Integer, default=0)     # Files uploaded
    max_files_trial = Column(Integer, default=5)          # Limit: 5 files max
    
    # Anti-abuse: track daily usage to prevent "one-day sprint"
    last_report_generated_at = Column(DateTime(timezone=True), nullable=True)
    daily_report_count = Column(Integer, default=0)
    daily_report_reset_date = Column(Date, nullable=True)  # Reset counter daily
    
    # Relationships
    files = relationship("UploadedFile", back_populates="user", cascade="all, delete-orphan")
    dashboards = relationship("Dashboard", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    templates = relationship("ReportTemplate", back_populates="user", cascade="all, delete-orphan")


class UploadedFile(Base):
    """Uploaded 1C file model."""
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)  # in bytes
    file_type = Column(String(50), nullable=False)  # xlsx, xls, csv
    upload_status = Column(String(50), default="pending")  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)
    
    # Processing metadata
    rows_count = Column(Integer, nullable=True)
    columns_count = Column(Integer, nullable=True)
    detected_columns = Column(JSON, nullable=True)  # AI detection results
    business_rules_applied = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="files")
    forecasts = relationship("Forecast", back_populates="file", cascade="all, delete-orphan")


class Dashboard(Base):
    """Dashboard configuration model."""
    __tablename__ = "dashboards"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_public = Column(Boolean, default=False)
    
    # Configuration
    config = Column(JSON, nullable=False, default=dict)  # Dashboard layout and settings
    filters = Column(JSON, nullable=True)  # Applied filters
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="dashboards")


class Forecast(Base):
    """Forecast results model."""
    __tablename__ = "forecasts"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("uploaded_files.id"), nullable=False)
    model_type = Column(String(50), nullable=False)  # naive, prophet, xgboost, ensemble
    target_column = Column(String(255), nullable=False)
    
    # Forecast parameters
    periods = Column(Integer, nullable=False)
    confidence_levels = Column(JSON, nullable=True)  # [0.8, 0.95]
    parameters = Column(JSON, nullable=True)
    
    # Results
    forecast_values = Column(JSON, nullable=False)  # Predicted values
    confidence_intervals = Column(JSON, nullable=True)  # Upper/lower bounds
    metrics = Column(JSON, nullable=True)  # MAE, RMSE, MAPE, etc.
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    file = relationship("UploadedFile", back_populates="forecasts")


class APIKey(Base):
    """API Key for programmatic access."""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    key_hash = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Permissions
    scopes = Column(JSON, nullable=True)  # ["read", "write", "admin"]
    
    # Usage tracking
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    usage_count = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="api_keys")


class AuditLog(Base):
    """Audit log for security and compliance."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)  # login, upload, forecast, export, etc.
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(Integer, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    status = Column(String(20), nullable=False)  # success, failure
    details = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ReportTemplate(Base):
    """Saved report template for reuse."""
    __tablename__ = "report_templates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Template configuration
    template_config = Column(JSON, nullable=False, default=dict)  # Layout, charts, filters
    source_file_structure = Column(JSON, nullable=True)  # Expected column structure
    
    # Usage stats
    times_used = Column(Integer, default=0)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="templates")
