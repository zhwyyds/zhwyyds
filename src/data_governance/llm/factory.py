from __future__ import annotations

import logging
from typing import Protocol

from data_governance.config_loader import ModelConfig
from data_governance.llm.anthropic_client import AnthropicMessagesClient
from data_governance.llm.env import provider_api_key
from data_governance.llm.openai_client import DEFAULT_QWEN_BASE, DEFAULT_ZHIPU_BASE, OpenAIChatClient

logger = logging.getLogger(__name__)


class PromptLLM(Protocol):
    model_name: str

    def complete(self, prompt: str) -> str: ...


def _openai_base(cfg: ModelConfig) -> str:
    if cfg.api_endpoint:
        return cfg.api_endpoint.rstrip("/")
    p = cfg.provider.lower()
    if p in ("zhipuai", "zhipu", "glm"):
        return DEFAULT_ZHIPU_BASE
    if p in ("qwen", "dashscope", "alibaba", "tongyi"):
        return DEFAULT_QWEN_BASE
    return ""


def build_live_client(cfg: ModelConfig) -> PromptLLM | None:
    key = provider_api_key(cfg.provider, env_var=cfg.api_key_env or None)
    if not key:
        logger.warning("skip model %s: no API key for provider %s", cfg.model_name, cfg.provider)
        return None
    p = cfg.provider.lower()
    if p == "anthropic":
        return AnthropicMessagesClient(cfg.model_name, api_key=key)
    if p in ("openai", "zhipuai", "zhipu", "glm", "qwen", "dashscope", "alibaba", "tongyi") or cfg.api_endpoint:
        return OpenAIChatClient(
            cfg.model_name,
            api_key=key,
            base_url=_openai_base(cfg) or None,
        )
    logger.warning("unknown provider %s for model %s", cfg.provider, cfg.model_name)
    return None


def build_live_clients(configs: list[ModelConfig], *, min_clients: int = 1) -> list[PromptLLM]:
    """构建 live 客户端。min_clients=1 支持单模型模式（用户仅有 1 家 Key 时）；≥2 家时并行比对。"""
    clients: list[PromptLLM] = []
    for cfg in configs:
        c = build_live_client(cfg)
        if c is not None:
            clients.append(c)
    if len(clients) < min_clients:
        raise RuntimeError(
            f"M3 live mode needs at least {min_clients} models with API keys; "
            f"configured {len(clients)}. Set keys in env, .env, or config/secrets.json "
            "(see config/secrets.example.json); or use DATA_GOV_LLM_MODE=mock."
        )
    return clients
