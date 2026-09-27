"""Behaviour: log records are JSON and secrets/emails are redacted."""

import importlib
import json
import logging
from io import StringIO
from pathlib import Path

import pytest
from opentelemetry.sdk.trace import TracerProvider

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


def _format(record: logging.LogRecord) -> dict[str, object]:
    import bas_assistant.logging as log_mod  # noqa: PLC0415

    formatted: dict[str, object] = json.loads(log_mod.JsonFormatter().format(record))
    return formatted


def test_log_line_carries_the_request_id_it_was_given() -> None:
    record = logging.makeLogRecord(
        {"msg": "request closed", "levelno": logging.INFO, "request_id": "req-123"}
    )

    assert _format(record)["request_id"] == "req-123"


def test_log_line_inside_a_span_carries_the_trace_id() -> None:
    tracer = TracerProvider().get_tracer("test")
    with tracer.start_as_current_span("request") as span:
        payload = _format(logging.makeLogRecord({"msg": "inside", "levelno": logging.INFO}))

    assert payload["trace_id"] == format(span.get_span_context().trace_id, "032x")


def test_log_line_outside_a_span_has_no_trace_id() -> None:
    payload = _format(logging.makeLogRecord({"msg": "outside", "levelno": logging.INFO}))

    assert "trace_id" not in payload
