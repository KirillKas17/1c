"""
Prometheus Metrics for Dashboard Application.
Provides monitoring endpoints and metrics collection.
"""
import time
import threading
from typing import Dict, Optional, Callable
from functools import wraps
from prometheus_client import (
    Counter, Gauge, Histogram, Summary,
    generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry
)
from datetime import datetime

# Define metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

REQUEST_IN_PROGRESS = Gauge(
    'http_requests_in_progress',
    'Number of HTTP requests currently being processed',
    ['method', 'endpoint']
)

# Business metrics
DOCUMENTS_PROCESSED = Counter(
    'documents_processed_total',
    'Total documents processed',
    ['document_type', 'status']
)

PARSING_DURATION = Summary(
    'parsing_duration_seconds',
    'Time spent parsing documents',
    ['document_type']
)

ACTIVE_USERS = Gauge(
    'active_users',
    'Number of active users'
)

ERROR_COUNT = Counter(
    'errors_total',
    'Total errors',
    ['error_type', 'component']
)

EXPORT_COUNT = Counter(
    'exports_total',
    'Total exports by format',
    ['format']
)

CACHE_METRICS = {
    'hits': Counter('cache_hits_total', 'Total cache hits'),
    'misses': Counter('cache_misses_total', 'Total cache misses'),
    'size': Gauge('cache_size', 'Current cache size')
}


class MetricsMiddleware:
    """ASGI/WSGI middleware for collecting HTTP metrics."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        
        method = scope['method']
        path = scope['path']
        
        # Track in-progress requests
        REQUEST_IN_PROGRESS.labels(method=method, endpoint=path).inc()
        
        start_time = time.time()
        status_code = 500
        
        try:
            async def send_wrapper(message):
                nonlocal status_code
                if message['type'] == 'http.response.start':
                    status_code = message['status']
                await send(message)
            
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.time() - start_time
            REQUEST_IN_PROGRESS.labels(method=method, endpoint=path).dec()
            REQUEST_COUNT.labels(method=method, endpoint=path, status=status_code).inc()
            REQUEST_DURATION.labels(method=method, endpoint=path).observe(duration)


def track_metrics(metric_name: str, labels: Optional[Dict[str, str]] = None):
    """Decorator to track function execution metrics."""
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                ERROR_COUNT.labels(error_type=type(e).__name__, component=func.__module__).inc()
                raise
            finally:
                duration = time.time() - start_time
                metric = globals().get(metric_name)
                if metric and isinstance(metric, Summary):
                    metric.observe(duration, labels=labels or {})
                elif metric and isinstance(metric, Histogram):
                    metric.observe(duration)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                ERROR_COUNT.labels(error_type=type(e).__name__, component=func.__module__).inc()
                raise
            finally:
                duration = time.time() - start_time
                metric = globals().get(metric_name)
                if metric and isinstance(metric, Summary):
                    metric.observe(duration, labels=labels or {})
                elif metric and isinstance(metric, Histogram):
                    metric.observe(duration)
        
        return async_wrapper if threading.current_thread().__class__.__name__ == 'Thread' else sync_wrapper
    return decorator


def get_metrics_endpoint():
    """Generate Prometheus metrics endpoint response."""
    return generate_latest(), {'Content-Type': CONTENT_TYPE_LATEST}


def update_cache_metrics(hits: int = 0, misses: int = 0, size: int = 0):
    """Update cache-related metrics."""
    if hits > 0:
        CACHE_METRICS['hits'].inc(hits)
    if misses > 0:
        CACHE_METRICS['misses'].inc(misses)
    if size >= 0:
        CACHE_METRICS['size'].set(size)


def track_document_processing(doc_type: str, status: str, duration: float):
    """Track document processing metrics."""
    DOCUMENTS_PROCESSED.labels(document_type=doc_type, status=status).inc()
    PARSING_DURATION.labels(document_type=doc_type).observe(duration)


def track_export(format_type: str):
    """Track export operations."""
    EXPORT_COUNT.labels(format=format_type).inc()


class HealthChecker:
    """Application health check with metrics."""
    
    def __init__(self):
        self.last_check = None
        self.health_status = 'unknown'
        self.components = {}
    
    def register_component(self, name: str, check_func: Callable):
        """Register a health check component."""
        self.components[name] = check_func
    
    async def check_health(self) -> Dict:
        """Perform health check on all components."""
        results = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'components': {}
        }
        
        overall_healthy = True
        
        for name, check_func in self.components.items():
            try:
                is_healthy = await check_func() if hasattr(check_func, '__await__') else check_func()
                results['components'][name] = {
                    'status': 'healthy' if is_healthy else 'unhealthy',
                    'healthy': is_healthy
                }
                if not is_healthy:
                    overall_healthy = False
            except Exception as e:
                results['components'][name] = {
                    'status': 'error',
                    'healthy': False,
                    'error': str(e)
                }
                overall_healthy = False
        
        results['status'] = 'healthy' if overall_healthy else 'unhealthy'
        self.last_check = datetime.now()
        self.health_status = results['status']
        
        return results
    
    def get_health_gauge(self) -> float:
        """Return health status as gauge (1=healthy, 0=unhealthy)."""
        return 1.0 if self.health_status == 'healthy' else 0.0


# Global health checker instance
health_checker = HealthChecker()
