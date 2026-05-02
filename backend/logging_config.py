import json
import logging
import os
from datetime import datetime, timezone

_SKIP_FIELDS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()) | {
    "message", "asctime", "exc_text", "stack_info",
}


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        log: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.%f"
            )[:-3] + "Z",
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.message,
        }
        for key, value in record.__dict__.items():
            if key not in _SKIP_FIELDS and not key.startswith("_"):
                log[key] = value
        if record.exc_info:
            log["exc"] = self.formatException(record.exc_info)
        return json.dumps(log, ensure_ascii=False)


def setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    logging.basicConfig(level=level, handlers=[handler], force=True)
