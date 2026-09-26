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

    # Non-secret operational config
    daily_usd_cap: Decimal = Decimal("3")
