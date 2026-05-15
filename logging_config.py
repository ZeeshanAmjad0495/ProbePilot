import datetime
import json
import logging
import sys

STANDARD_LOG_ATTRS = frozenset(
    [
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "process",
        "processName",
        "message",
        "asctime",
        "taskName",
    ]
)


class JsonFormatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        return datetime.datetime.fromtimestamp(
            record.created, tz=datetime.timezone.utc
        ).isoformat()

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in STANDARD_LOG_ATTRS:
                log_obj[key] = value
        return json.dumps(log_obj, default=str)


def setup_logging() -> None:
    """Configure root logger to emit JSON lines. Idempotent."""
    root = logging.getLogger()
    if getattr(root, "_probepilot_json_configured", False):
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root.handlers = [handler]
    root.setLevel(logging.INFO)

    root._probepilot_json_configured = True  # type: ignore[attr-defined]
