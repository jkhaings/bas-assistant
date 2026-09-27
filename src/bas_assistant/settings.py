"""Application settings — reads from os.environ only; never from .env files.

Load with ``Settings()``. SecretStr fields mask repr and model_dump output
automatically. Use ``settings.openai_api_key.get_secret_value()`` only where
the raw value is needed (e.g. passed to a library).
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration drawn from environment variables.

    All secret fields use ``SecretStr`` so they never appear in logs or repr.
    The app reads this class exactly once at startup; never pass it through
    more than one layer — extract the value you need at the call site.
    """

    model_config = SettingsConfigDict(
        env_file=None,  # no .env file — load from os.environ only
        secrets_dir=None,  # no secrets dir
        extra="ignore",  # ignore unrecognised env vars
    )

    # TODO(session E): only the LiteLLM container needs vendor keys; split the env files.
    openai_api_key: SecretStr
    anthropic_api_key: SecretStr
    gemini_api_key: SecretStr
    admin_token: SecretStr
    # Project keys of the self-hosted Langfuse (`make observability-secrets`); without them
    # tracing is off, as in unit tests and CI.
    langfuse_public_key: SecretStr | None = None
    langfuse_secret_key: SecretStr | None = None
    grafana_admin_password: SecretStr
    postgres_password: SecretStr
    # Virtual key the app presents to the LiteLLM proxy; its budget lives in the proxy.
    litellm_api_key: SecretStr

    # Non-secret operational config. URL defaults are the docker compose service names.
    daily_usd_cap: Decimal = Decimal("3")
    user_daily_questions: int = 50
    # Per IP per minute. Every visitor of a role shares its demo user, so this is the
    # per-visitor control on the public link.
    ip_rate_limit: int = 20
    # Part of the answer-cache key: bump when the corpus or the retrieval over it changes, so
    # no stale answer survives ("2": the session D reranker).
    corpus_version: str = "2"
    redis_url: str = "redis://redis:6379/0"
    litellm_base_url: str = "http://litellm:4000"
    langfuse_host: str = "http://langfuse-web:3000"

    # Postgres — host/port default to the compose service name and its internal
    # port; integration tests override via env to reach the published host port.
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_user: str = "bas_assistant"
    postgres_db: str = "bas_assistant"

    # Embeddings go through the LiteLLM proxy's `embed` alias, like every model call.
    embed_base_url: str = "http://litellm:4000/v1"
    embed_model: str = "embed"
    # Used only if the proxy response carries no x-litellm-response-cost header.
    embed_usd_per_mtok: Decimal = Decimal("0.02")

    # Retrieval. MiniLM replaced bge-reranker-base in session D: 13-20 s per question on
    # the container's CPU against a 3 s budget (docs/adr/0003-reranker.md). It reads each
    # chunk with its document title (session C).
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    # THRESHOLD_PENDING
    rerank_threshold: float = 0.8

    @property
    def database_url(self) -> str:
        """Postgres DSN for SQLAlchemy, using the psycopg 3 driver."""
        return (
            f"postgresql+psycopg://{self.postgres_user}:"
            f"{self.postgres_password.get_secret_value()}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
