"""
Pydantic схемы для API валидации
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


class SubscriptionTier(str, Enum):
    FREE = "free"
    STARTER = "starter"  # 990₽
    PROFESSIONAL = "professional"  # 4900₽
    ENTERPRISE = "enterprise"  # 19900₽


# === Auth Schemas ===

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    company_name: Optional[str] = None
    industry: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    user_id: int
    email: str
    role: UserRole
    exp: datetime


class UserResponse(BaseModel):
    id: int
    email: str
    company_name: Optional[str]
    subscription_tier: SubscriptionTier
    subscription_expires: Optional[datetime]
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


# === File Upload Schemas ===

class FileUploadResponse(BaseModel):
    file_id: str
    filename: str
    size_bytes: int
    rows_count: int
    columns_count: int
    detected_format: str
    upload_timestamp: datetime
    status: str = "processing"


class FileStatusResponse(BaseModel):
    file_id: str
    status: str  # processing, ready, error
    progress: int  # 0-100
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


# === Dashboard Schemas ===

class DashboardConfig(BaseModel):
    industry: Optional[str] = None
    date_column: Optional[str] = None
    value_columns: List[str] = []
    group_columns: List[str] = []
    forecast_periods: int = 12
    confidence_level: float = 0.95
    chart_types: Dict[str, str] = {}  # metric -> chart_type


class DashboardResponse(BaseModel):
    dashboard_id: str
    file_id: str
    title: str
    created_at: datetime
    metrics: List[Dict[str, Any]]
    charts: List[Dict[str, Any]]
    forecasts: List[Dict[str, Any]]
    insights: List[str]
    recommendations: List[str]


class MetricData(BaseModel):
    name: str
    value: float
    unit: str
    trend: str  # up, down, stable
    change_percent: float
    forecast: Optional[List[float]] = None
    confidence_interval: Optional[Dict[str, List[float]]] = None


# === Payment Schemas ===

class SubscriptionPlan(BaseModel):
    tier: SubscriptionTier
    price: int
    currency: str = "RUB"
    billing_period: str = "month"
    features: List[str]
    limits: Dict[str, Any]


class PaymentIntent(BaseModel):
    payment_id: str
    amount: int
    currency: str
    description: str
    customer_email: EmailStr
    return_url: str
    status: str = "pending"


class PaymentWebhook(BaseModel):
    event_type: str  # payment.succeeded, payment.canceled, etc.
    payment_id: str
    amount: int
    status: str
    metadata: Optional[Dict[str, Any]] = None


# === Health Check ===

class HealthCheck(BaseModel):
    status: str
    version: str
    timestamp: datetime
    services: Dict[str, str]
