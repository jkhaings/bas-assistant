"""Behaviour: log records are JSON and secrets/emails are redacted."""

import importlib
import json
import logging
from io import StringIO
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_FIXTURE = Path(__file__).parent / "fixtures" / "fake_keys.txt"


def _fake_key() -> str:
    """Read the first key-shaped fake value from the fixture file."""
    for line in _FIXTURE.read_text().splitlines():
        if line.startswith("FAKE_OPENAI="):
            return line.split("=", 1)[1]
    raise AssertionError("fixture not found")


def test_log_line_is_json_with_keys_and_emails_redacted() -> None:
    buf = StringIO()
    handler = logging.StreamHandler(buf)

    # Re-import to get fresh module state
    import bas_assistant.logging as log_mod  # noqa: PLC0415

    importlib.reload(log_mod)

    handler.addFilter(log_mod.RedactingFilter())
    handler.setFormatter(log_mod.JsonFormatter())

    logger = logging.getLogger("test_redact")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    key = _fake_key()
    logger.info("key=%s email=user@example.com", key)

    output = buf.getvalue().strip()
    record = json.loads(output)

    assert record["level"] == "INFO"
    assert "ts" in record
    assert key not in record["message"], "key leaked into log"
    assert "user@example.com" not in record["message"], "email leaked into log"
    assert "[REDACTED]" in record["message"]
