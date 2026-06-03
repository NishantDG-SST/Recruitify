import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict


class StructuredJSONFormatter(logging.Formatter):
    """Format logs as structured JSON."""
    
    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
            
        # Add any extra contextual fields bound to the logger
        if hasattr(record, "context"):
            log_entry.update(record.context)

        return json.dumps(log_entry)


def setup_structured_logging(service_name: str, level: int = logging.INFO) -> None:
    """Configure the root logger to output structured JSON."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredJSONFormatter(service_name))
    root_logger.addHandler(handler)


class ContextAdapter(logging.LoggerAdapter):
    """Adapter to automatically inject context into structured logs."""
    
    def process(self, msg: Any, kwargs: Dict[str, Any]) -> tuple[Any, Dict[str, Any]]:
        if "extra" not in kwargs:
            kwargs["extra"] = {}
        
        # Attach our bound context to the record so the formatter can extract it
        kwargs["extra"]["context"] = self.extra
        return msg, kwargs

def get_logger(name: str, **context_kwargs: Any) -> ContextAdapter:
    """Get a logger instance with optional bound context (e.g. run_id=...)."""
    logger = logging.getLogger(name)
    return ContextAdapter(logger, context_kwargs)
