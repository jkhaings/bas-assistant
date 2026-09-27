"""Register the LiteLLM virtual keys with their monthly budgets. Run with `make litellm-keys`.

Key values come from the environment (never from a file in the repo), so re-running
updates the budgets in place instead of minting new keys.
"""

import logging
import os

import httpx

from bas_assistant.logging import configure_logging

logger = logging.getLogger(__name__)

# (alias, env var holding the key, monthly USD budget)
VIRTUAL_KEYS = (
    ("dev", "LITELLM_API_KEY", 5.0),
    ("service", "LITELLM_SERVICE_KEY", 2.0),
)


def register(client: httpx.Client, alias: str, key: str, monthly_usd: float) -> None:
    body = {"key": key, "key_alias": alias, "max_budget": monthly_usd, "budget_duration": "30d"}
    if client.post("/key/generate", json=body).is_success:
        logger.info("created virtual key %s with $%s/month", alias, monthly_usd)
        return
    client.post("/key/update", json=body).raise_for_status()
    logger.info("updated virtual key %s to $%s/month", alias, monthly_usd)


def main() -> None:
    configure_logging()
    master = os.environ["LITELLM_MASTER_KEY"]
    with httpx.Client(
        base_url=os.environ["LITELLM_BASE_URL"],
        headers={"Authorization": f"Bearer {master}"},
        timeout=30,
    ) as client:
        for alias, env_var, monthly_usd in VIRTUAL_KEYS:
            register(client, alias, os.environ[env_var], monthly_usd)


if __name__ == "__main__":
    main()
