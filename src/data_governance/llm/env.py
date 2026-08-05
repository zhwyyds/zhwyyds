from __future__ import annotations

import os


def llm_mode_from_env() -> str:
    """mock | live | auto (default auto)."""
    return (os.environ.get("DATA_GOV_LLM_MODE") or "auto").strip().lower()


def provider_api_key(provider: str, *, env_var: str | None = None) -> str | None:
    if env_var:
        direct = (os.environ.get(env_var) or "").strip()
        if direct:
            return direct
    p = (provider or "").strip().lower()
    if p in ("openai",):
        return os.environ.get("OPENAI_API_KEY") or os.environ.get("DATA_GOV_OPENAI_API_KEY")
    if p in ("anthropic",):
        return os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("DATA_GOV_ANTHROPIC_API_KEY")
    if p in ("zhipuai", "zhipu", "glm"):
        return (
            os.environ.get("ZHIPUAI_API_KEY")
            or os.environ.get("GLM_API_KEY")
            or os.environ.get("DATA_GOV_ZHIPUAI_API_KEY")
        )
    if p in ("qwen", "dashscope", "alibaba", "tongyi"):
        return (
            os.environ.get("DASHSCOPE_API_KEY")
            or os.environ.get("QWEN_API_KEY")
            or os.environ.get("DATA_GOV_QWEN_API_KEY")
            or os.environ.get("DATA_GOV_DASHSCOPE_API_KEY")
        )
    return os.environ.get(f"DATA_GOV_{p.upper()}_API_KEY") if p else None


def any_live_provider_configured() -> bool:
    return any(provider_api_key(p) for p in ("OpenAI", "Anthropic", "Qwen", "ZhipuAI"))


def resolve_use_mock(explicit: bool | None = None) -> bool:
    if explicit is not None:
        return explicit
    mode = llm_mode_from_env()
    if mode == "mock":
        return True
    if mode == "live":
        return False
    return not any_live_provider_configured()
