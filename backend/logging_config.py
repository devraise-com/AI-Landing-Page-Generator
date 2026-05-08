import logging
import os

_STANDARD_FIELDS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()) | {
    "message",
    "asctime",
}


class _StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras = {k: v for k, v in record.__dict__.items() if k not in _STANDARD_FIELDS}
        if not extras:
            return base
        parts = " ".join(f"{k}={v}" for k, v in extras.items())
        return f"{base} {parts}"


def setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    formatter = _StructuredFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)
