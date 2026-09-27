"""One client to the running stack for the whole eval run, paced to the app's per-IP limit:
every module's requests come from the same address, so they share one budget."""

from collections.abc import Iterator

import httpx
import pytest

from bas_assistant.evals.pacing import pacing_hook
from bas_assistant.guardrails.limits import RATE_WINDOW
from bas_assistant.settings import Settings

APP_URL = "http://localhost:8000"
# Above the app's worst case: the router and the answer call can each take 130 s through the
# proxy's fallbacks, plus the CPU reranker.
TIMEOUT_S = 330


@pytest.fixture(scope="session")
def app() -> Iterator[httpx.Client]:
    # The app stamps each request after it is sent; a second of slack keeps the oldest one out
    # of the app's window by the time the next one arrives.
    hook = pacing_hook(Settings().ip_rate_limit, RATE_WINDOW.total_seconds() + 1)
    with httpx.Client(
        base_url=APP_URL, timeout=TIMEOUT_S, event_hooks={"request": [hook]}
    ) as client:
        yield client
