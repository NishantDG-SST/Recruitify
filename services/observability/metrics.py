import time
from typing import Callable, Dict, Any
from functools import wraps
import logging

from services.observability.logger import get_logger

# Simple in-memory metrics registry for MVP (would normally be Prometheus/StatsD)
_METRICS: Dict[str, float] = {}
logger = get_logger(__name__)

def increment_counter(metric_name: str, value: float = 1.0, tags: Dict[str, str] = None) -> None:
    """Increment a counter metric."""
    tag_str = ",".join(f"{k}={v}" for k, v in (tags or {}).items())
    full_name = f"{metric_name}[{tag_str}]" if tag_str else metric_name
    
    if full_name not in _METRICS:
        _METRICS[full_name] = 0.0
    _METRICS[full_name] += value
    
    # Also log it for structured scraping
    logger.info("Metric increment", metric_name=metric_name, value=value, tags=tags)


def record_latency(metric_name: str, duration_ms: float, tags: Dict[str, str] = None) -> None:
    """Record a latency/timing metric."""
    # In a real system, this would go to a histogram/summary
    tag_str = ",".join(f"{k}={v}" for k, v in (tags or {}).items())
    full_name = f"{metric_name}_ms[{tag_str}]" if tag_str else f"{metric_name}_ms"
    
    _METRICS[full_name] = duration_ms
    logger.info("Latency recorded", metric_name=metric_name, duration_ms=duration_ms, tags=tags)


def track_latency(metric_name: str, tags: Dict[str, str] = None) -> Callable:
    """Decorator to automatically track latency of a function."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000
                record_latency(metric_name, duration_ms, tags)
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                record_latency(f"{metric_name}_error", duration_ms, tags)
                raise e
        return wrapper
    return decorator


def dump_metrics() -> Dict[str, float]:
    """Get all current metrics (useful for a /metrics endpoint)."""
    return _METRICS.copy()
