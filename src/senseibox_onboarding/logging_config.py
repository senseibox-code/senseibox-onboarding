from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path


REDACTED_WORDS = ("password", "psk", "secret", "token")


class SecretFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if any(word in message.lower() for word in REDACTED_WORDS):
            record.msg = "[redacted sensitive log message]"
            record.args = ()
        return True


def configure_logging(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=512_000,
        backupCount=4,
        encoding="utf-8",
    )
    handler.addFilter(SecretFilter())
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
