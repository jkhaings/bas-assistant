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

    openai_api_key: SecretStr
    anthropic_api_key: SecretStr
    gemini_api_key: SecretStr
    admin_token: SecretStr
    # Minted by the self-hosted Langfuse instance in session D; optional until then.
    langfuse_public_key: SecretStr | None = None
    langfuse_secret_key: SecretStr | None = None
    grafana_admin_password: SecretStr
    postgres_password: SecretStr

    # Non-secret operational config
    daily_usd_cap: Decimal = Decimal("3")

    # Postgres — host/port default to the compose service name and its internal
    # port; integration tests override via env to reach the published host port.
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_user: str = "bas_assistant"
    postgres_db: str = "bas_assistant"

    # Embedding provider — session B repoints these at the LiteLLM proxy's
    # `embed` alias by env change only; no code here talks to a vendor SDK.
    embed_base_url: str = "https://api.openai.com/v1"
    embed_model: str = "text-embedding-3-small"
    embed_usd_per_mtok: Decimal = Decimal("0.02")

    # Retrieval
    rerank_model: str = "BAAI/bge-reranker-base"
    # Tuned in session A against the real corpus (see data/top20_questions.md):
    # the 15 answerable questions' top score was 0.55-0.99; the out-of-scope
    # and ACL-blocked-role cases topped out at 0.46. Below this, /ask abstains.
    rerank_threshold: float = 0.5

    @property
    def database_url(self) -> str:
        """Postgres DSN for SQLAlchemy, using the psycopg 3 driver."""
        return (
            f"postgresql+psycopg://{self.postgres_user}:"
            f"{self.postgres_password.get_secret_value()}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
