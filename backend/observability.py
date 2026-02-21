import json
import logging
import time
import uuid
from typing import Any, Dict, Optional

from backend.config import config


def _json_formatter(record: logging.LogRecord) -> str:
    payload = {
        "level": record.levelname,
        "msg": record.getMessage(),
        "time": int(time.time() * 1000),
    }
    if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
        payload.update(record.extra_fields)
    return json.dumps(payload, ensure_ascii=True)


def configure_logging() -> None:
    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(level=level)
    root = logging.getLogger()
    fmt = _json_formatter if config.LOG_FORMAT == "json" else None
    if fmt:
        for h in root.handlers:
            h.setFormatter(logging.Formatter(fmt="%(message)s"))
        root.handlers = [logging.StreamHandler()]
        for h in root.handlers:
            h.setFormatter(logging.Formatter(fmt="%(message)s"))
    # Ensure our app logger exists
    logger = logging.getLogger("syllabus_sync")
    logger.setLevel(level)


def log_struct(event: str, **fields: Any) -> None:
    logger = logging.getLogger("syllabus_sync")
    redacted = {k: v for k, v in fields.items() if k not in {"prompt", "response", "tmp_path", "raw_text"}}
    record = logging.LogRecord(
        name=logger.name,
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg=event,
        args=(),
        exc_info=None,
    )
    record.extra_fields = redacted
    logger.handle(record)


class Metrics:
    def __init__(self):
        self.counters: Dict[str, float] = {}
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, list] = {}

    def clear(self) -> None:
        self.counters.clear()
        self.gauges.clear()
        self.histograms.clear()

    def inc(self, name: str, value: float = 1.0, **labels):
        if not config.ENABLE_METRICS:
            return
        key = self._key(name, labels)
        self.counters[key] = self.counters.get(key, 0.0) + value

    def set_gauge(self, name: str, value: float, **labels):
        if not config.ENABLE_METRICS:
            return
        key = self._key(name, labels)
        self.gauges[key] = value

    def observe(self, name: str, value: float, **labels):
        if not config.ENABLE_METRICS:
            return
        key = self._key(name, labels)
        self.histograms.setdefault(key, []).append(value)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": {k: list(v) for k, v in self.histograms.items()},
        }

    def _key(self, name: str, labels: Dict[str, Any]) -> str:
        if not labels:
            return name
        parts = [name] + [f"{k}={v}" for k, v in sorted(labels.items())]
        return ",".join(parts)


metrics = Metrics()


def clear_metrics() -> None:
    metrics.clear()


def new_trace_id() -> str:
    return uuid.uuid4().hex


class TraceContext:
    def __init__(self, trace_id: Optional[str] = None):
        self.trace_id = trace_id or new_trace_id()

    def as_dict(self):
        return {"trace_id": self.trace_id}
