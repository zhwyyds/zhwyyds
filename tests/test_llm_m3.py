from __future__ import annotations

import json

import httpx
import pytest

from data_governance.llm.env import resolve_use_mock
from data_governance.llm.openai_client import OpenAIChatClient


def test_resolve_use_mock_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATA_GOV_LLM_MODE", raising=False)
    assert resolve_use_mock(True) is True
    assert resolve_use_mock(False) is False


def test_resolve_use_mock_mode_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_GOV_LLM_MODE", "mock")
    assert resolve_use_mock(None) is True


def test_resolve_use_mock_mode_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_GOV_LLM_MODE", "live")
    assert resolve_use_mock(None) is False


def test_resolve_use_mock_auto_no_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_GOV_LLM_MODE", "auto")
    for key in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "DASHSCOPE_API_KEY",
        "QWEN_API_KEY",
        "ZHIPUAI_API_KEY",
        "GLM_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    assert resolve_use_mock(None) is True


def test_qwen_provider_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-dash")
    from data_governance.llm.env import provider_api_key

    assert provider_api_key("Qwen") == "sk-dash"
    assert provider_api_key("Qwen", env_var="DASHSCOPE_API_KEY") == "sk-dash"


def test_openai_chat_client_mock_transport() -> None:
    payload = {"choices": [{"message": {"content": '[{"cn_term":"客户","root_en":"customer"}]'}}]}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        body = json.loads(request.content.decode())
        assert body["model"] == "gpt-4o"
        assert body["messages"][0]["content"] == "hello"
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    client = OpenAIChatClient("gpt-4o", api_key="sk-test", transport=transport)
    assert client.complete("hello") == payload["choices"][0]["message"]["content"]
