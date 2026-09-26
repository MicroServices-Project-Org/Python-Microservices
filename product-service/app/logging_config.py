import logging
import os
import sys
import threading
import time
from pathlib import Path

from opentelemetry import trace as _trace
from pythonjsonlogger import jsonlogger

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = Path(os.getenv("LOG_DIR", _PROJECT_ROOT / "logs"))

# While Kafka is unreachable, aiokafka retries every ~100ms and logs each failure at ERROR,
# which wrote ~700 MB/service to logs/ during an outage. Keep the first occurrence of each
# message, then drop repeats for this many seconds and report how many were dropped.
KAFKA_LOG_THROTTLE_SECONDS = 60


class RepeatThrottleFilter(logging.Filter):
    """Rate-limits repeated WARNING+ records from `prefix` loggers, keyed by logger + message template."""

    def __init__(self, prefix: str = "aiokafka", window: float = KAFKA_LOG_THROTTLE_SECONDS):
        super().__init__()
        self.prefix = prefix
        self.window = window
        self._lock = threading.Lock()
        self._last_emit: dict[tuple, float] = {}
        self._suppressed: dict[tuple, int] = {}

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno < logging.WARNING or not record.name.startswith(self.prefix):
            return True
        # Attached to several handlers: decide once per record, then reuse the decision
        decision = getattr(record, "_throttle_keep", None)
        if decision is not None:
            return decision
        record._throttle_keep = self._decide(record)
        return record._throttle_keep

    def _decide(self, record: logging.LogRecord) -> bool:
        key = (record.name, record.levelno, str(record.msg))  # template, so changing args still match
        now = time.monotonic()
        with self._lock:
            last = self._last_emit.get(key)
            if last is not None and now - last < self.window:
                self._suppressed[key] = self._suppressed.get(key, 0) + 1
                return False
            self._last_emit[key] = now
            dropped = self._suppressed.pop(key, 0)
        if dropped:
            record.suppressed_repeats = dropped
            record.msg = f"{record.msg} [{dropped} similar messages suppressed since the last one]"
        return True


def setup_logging(service_name: str, level: str = "INFO") -> None:
    """JSON logging to stdout + file. Pulls trace_id/span_id from OTel current span."""
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s %(trace_id)s %(span_id)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
    )

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{service_name}.log"
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(formatter)

    class ContextFilter(logging.Filter):
        def filter(self, record):
            record.service = service_name
            span = _trace.get_current_span()
            ctx = span.get_span_context() if span else None
            if ctx and ctx.is_valid:
                record.trace_id = format(ctx.trace_id, "032x")
                record.span_id = format(ctx.span_id, "016x")
            else:
                record.trace_id = None
                record.span_id = None
            return True

    ctx_filter = ContextFilter()
    throttle = RepeatThrottleFilter()  # one shared instance, so both handlers drop the same records
    for handler in (stdout_handler, file_handler):
        handler.addFilter(throttle)
        handler.addFilter(ctx_filter)

    root_logger = logging.getLogger()
    root_logger.handlers = [stdout_handler, file_handler]
    root_logger.setLevel(level)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("aiokafka").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logging.info(
        f"Logging initialized for {service_name}",
        extra={"log_path": str(log_path)},
    )