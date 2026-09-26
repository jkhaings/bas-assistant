"""Structured JSON logging with secret and PII redaction.

Usage:
    from bas_assistant.logging import configure_logging
    configure_logging()  # call once at startup, before any log output

Rules (from CLAUDE.md):
- Never log request headers, raw env vars, settings objects, or raw questions.
- Only the Presidio-redacted question appears in logs.
"""

import json
import logging
import re
import sys
from typing import override

# One definition; hooks and pygrep patterns are kept identical.
_KEY_SHAPE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?:sk-(?:ant-|proj-)?[A-Za-z0-9_\-]{20,}"
    r"|AIza[0-9A-Za-z_\-]{35}"
    r"|ghp_[A-Za-z0-9]{36})"
)
_EMAIL = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def redact(text: str) -> str:
    """Replace key shapes and email addresses with [REDACTED]."""
    text = _KEY_SHAPE.sub("[REDACTED]", text)
    return _EMAIL.sub("[REDACTED]", text)


class RedactingFilter(logging.Filter):
    """Strip secrets and PII from log records in place."""

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        # Consume args first so getMessage() returns the fully-rendered string,
        # then redact the result and clear args so the formatter doesn't re-apply them.
        record.msg = redact(record.getMessage())
        record.args = ()
        if record.exc_text:
            record.exc_text = redact(record.exc_text)
        return True


class JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    @override
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: int = logging.INFO) -> None:
    """Set up JSON logging with the redacting filter on the root logger.

    Pass ``log_config=None`` to uvicorn so its records also flow here.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RedactingFilter())
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(handlers=[handler], level=level, force=True)
