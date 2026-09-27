"""Client-side pacing for runs against the app's per-IP limit (guardrails/limits.py).

The app sees every request from the dev host as one address (the compose network's gateway,
not 127.0.0.1), and no address is exempt, so an eval run has to stay under the limit itself.
"""

import time
from collections import deque
from collections.abc import Callable

import httpx


def pacing_hook(limit: int, window_s: float) -> Callable[[httpx.Request], None]:
    """An httpx request hook that sends at most `limit` requests in any `window_s` seconds."""
    starts: deque[float] = deque()

    def wait_for_slot(_request: httpx.Request) -> None:
        if len(starts) == limit:
            time.sleep(max(0.0, starts.popleft() + window_s - time.monotonic()))
        starts.append(time.monotonic())

    return wait_for_slot
