"""Prometheus metrics, the functions that feed them, and GET /metrics.

Labels stay low-cardinality (decision, route, stage, model, status). Per-user and per-team
numbers come from the Postgres views behind the Budget dashboard, never from labels.
"""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from bas_assistant.llm.gateway import Usage

# Past the 8 s p95 alert and the 13-20 s the reranker took before session D.
LATENCY_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1, 2, 3, 5, 8, 13, 21, 34, 55)
# Probes and scrapes would drown the API traffic the error-rate alert is about.
UNCOUNTED_PATHS = ("/healthz", "/metrics")

REQUESTS = Counter("bas_requests_total", "Requests closed, by decision", ["decision", "route"])
REQUEST_LATENCY = Histogram(
    "bas_request_latency_seconds", "Question to answer", ["route"], buckets=LATENCY_BUCKETS
)
STAGE_LATENCY = Histogram(
    "bas_stage_latency_seconds", "Time spent per stage", ["stage"], buckets=LATENCY_BUCKETS
)
TOKENS = Counter("bas_tokens_total", "Model tokens", ["model", "stage", "kind"])
USD = Counter("bas_usd_total", "Model spend in USD", ["model", "stage"])
CACHE_HITS = Counter("bas_cache_hits_total", "Answers served from the exact-match cache")
VALIDATION_RETRIES = Counter("bas_validation_retries_total", "Answers sent back by the validator")
VALIDATION_FAILURES = Counter(
    "bas_validation_failures_total", "Answers rejected twice and failed closed"
)
TICKETS = Counter("bas_tickets_total", "Ticket status changes", ["status"])
FEEDBACK = Counter("bas_feedback_total", "Answer feedback votes", ["value"])
FLAGS = Counter("bas_flags_total", "Answers flagged as wrong")
ACTIVE_THREADS = Gauge("bas_active_threads", "Threads with a turn running right now")
HTTP_REQUESTS = Counter("bas_http_requests_total", "API responses", ["method", "route", "status"])


def observe_request(route: str | None, decision: str, latency_ms: int) -> None:
    label = route or "none"
    REQUESTS.labels(decision, label).inc()
    REQUEST_LATENCY.labels(label).observe(latency_ms / 1000)


def observe_retrieval(retrieval_ms: int, rerank_ms: int) -> None:
    STAGE_LATENCY.labels("retrieval").observe(retrieval_ms / 1000)
    STAGE_LATENCY.labels("rerank").observe(rerank_ms / 1000)


def observe_model_call(stage: str, call: Usage) -> None:
    TOKENS.labels(call.model, stage, "input").inc(call.input_tokens)
    TOKENS.labels(call.model, stage, "output").inc(call.output_tokens)
    TOKENS.labels(call.model, stage, "cached").inc(call.cached_tokens)
    USD.labels(call.model, stage).inc(float(call.usd))
    STAGE_LATENCY.labels(stage).observe(call.latency_ms / 1000)


def observe_validation(answer_attempts: int, failed: bool) -> None:
    VALIDATION_RETRIES.inc(max(answer_attempts - 1, 0))
    if failed:
        VALIDATION_FAILURES.inc()


async def count_http_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """HTTP middleware: one count per API response, by route template and status."""
    if request.url.path in UNCOUNTED_PATHS:
        return await call_next(request)
    try:
        response = await call_next(request)
    except Exception:
        # Unhandled errors become a 500 outside this middleware; count them here.
        HTTP_REQUESTS.labels(request.method, _route(request), "500").inc()
        raise
    # The web app's static files and unknown paths match no API route; counted, they would
    # dilute the 5xx share the error-rate alert reads.
    if request.scope.get("route") is not None:
        HTTP_REQUESTS.labels(request.method, _route(request), str(response.status_code)).inc()
    return response


def _route(request: Request) -> str:
    # The path template ("/requests/{request_id}/receipt"), so ids never become labels.
    return str(getattr(request.scope.get("route"), "path", "unmatched"))


def metrics_endpoint() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
