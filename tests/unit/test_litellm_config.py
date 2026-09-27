"""Behaviour: config/litellm.yaml declares the aliases and fallback order of ARCHITECTURE.md."""

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

_CONFIG = yaml.safe_load(
    (Path(__file__).parents[2] / "config" / "litellm.yaml").read_text(encoding="utf-8")
)


def _deployments(name: str) -> list[str]:
    return [
        entry["litellm_params"]["model"]
        for entry in _CONFIG["model_list"]
        if entry["model_name"] == name
    ]


def _fallbacks() -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {}
    for rule in _CONFIG["router_settings"]["fallbacks"]:
        merged |= rule
    return merged


def test_fast_is_gpt4o_mini_falling_back_to_gemini_flash() -> None:
    assert _deployments("fast") == ["openai/gpt-4o-mini"]
    assert _fallbacks()["fast"] == ["fast-fallback"]
    assert _deployments("fast-fallback")[0].startswith("gemini/gemini-")


def test_strong_is_claude_sonnet_falling_back_to_gpt4o() -> None:
    assert _deployments("strong")[0].startswith("anthropic/claude-sonnet-")
    assert _fallbacks()["strong"] == ["strong-fallback", "fast"]
    assert _deployments("strong-fallback") == ["openai/gpt-4o"]


def test_embed_is_text_embedding_3_small() -> None:
    assert _deployments("embed") == ["openai/text-embedding-3-small"]


def test_deployment_ids_name_the_provider_and_model_the_gateway_reports() -> None:
    for entry in _CONFIG["model_list"]:
        assert entry["model_info"]["id"] == entry["litellm_params"]["model"]


def test_every_vendor_key_is_read_from_the_environment() -> None:
    for entry in _CONFIG["model_list"]:
        assert entry["litellm_params"]["api_key"].startswith("os.environ/")
    assert _CONFIG["general_settings"]["master_key"] == "os.environ/LITELLM_MASTER_KEY"
