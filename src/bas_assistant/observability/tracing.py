"""OpenTelemetry spans, exported to the self-hosted Langfuse over OTLP/HTTP.

Spans never carry prompts, completions, passages or the raw question. The trace input is
the redacted question, the same string written to `requests.question_redacted`.
"""

import base64
from decimal import Decimal
from uuid import UUID

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span

from bas_assistant.settings import Settings

# opentelemetry.util.types.AttributeValue is a chained assignment mypy cannot use as a type.
SpanAttributes = dict[str, str | bool | int | float]

tracer = trace.get_tracer("bas_assistant")


# The FastAPI instrumentation records these from the request; they are a header and the
# visitor's address, neither of which may leave the app (CLAUDE.md logging rule).
CLIENT_ATTRIBUTES = ("http.user_agent", "user_agent.original", "net.peer.ip", "client.address")


def langfuse_provider(settings: Settings) -> TracerProvider | None:
    """A provider that exports to Langfuse, or None without its keys (unit tests, CI)."""
    public = settings.langfuse_public_key
    secret = settings.langfuse_secret_key
    if not (public and public.get_secret_value() and secret and secret.get_secret_value()):
        return None
    credentials = f"{public.get_secret_value()}:{secret.get_secret_value()}".encode()
    exporter = OTLPSpanExporter(
        endpoint=f"{settings.langfuse_host}/api/public/otel/v1/traces",
        headers={
            "Authorization": f"Basic {base64.b64encode(credentials).decode()}",
            # Langfuse writes OTel spans straight through instead of batching them for minutes.
            "x-langfuse-ingestion-version": "4",
        },
    )
    provider = TracerProvider(resource=Resource.create({"service.name": "bas-assistant"}))
    provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider


def drop_client_details(span: Span, _scope: dict[str, object]) -> None:
    """FastAPI server_request_hook: blank the user agent and client address on the root span."""
    span.set_attributes(dict.fromkeys(CLIENT_ATTRIBUTES, ""))


def record_generation(
    span: Span, *, model: str, input_tokens: int, output_tokens: int, usd: Decimal
) -> None:
    """Mark a model-call span as a Langfuse generation with its tokens and cost."""
    span.set_attributes(
        {
            "langfuse.observation.type": "generation",
            "langfuse.observation.model.name": model,
            "gen_ai.usage.input_tokens": input_tokens,
            "gen_ai.usage.output_tokens": output_tokens,
            "gen_ai.usage.cost": float(usd),
        }
    )


def record_event(name: str, attributes: SpanAttributes) -> None:
    """A zero-length span Langfuse shows as an event, such as the gate pausing."""
    tracer.start_span(name, attributes={"langfuse.observation.type": "event", **attributes}).end()


def tag_trace(request_id: UUID, thread_id: UUID, role: str) -> None:
    """Group a thread's /ask and /approve traces into one Langfuse session."""
    trace.get_current_span().set_attributes(
        {
            "langfuse.session.id": str(thread_id),
            "langfuse.user.id": role,
            "langfuse.trace.metadata.request_id": str(request_id),
        }
    )


def set_trace_input(question_redacted: str) -> None:
    trace.get_current_span().set_attribute("langfuse.trace.input", question_redacted)


def set_trace_outcome(decision: str, route: str | None, answer: str, cache_hit: bool) -> None:
    trace.get_current_span().set_attributes(
        {
            "langfuse.trace.output": answer,
            "langfuse.trace.metadata.decision": decision,
            "langfuse.trace.metadata.route": route or "none",
            "langfuse.trace.metadata.cache_hit": cache_hit,
        }
    )
