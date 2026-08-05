from __future__ import annotations

from typing import Any

import httpx

DEFAULT_OPENAI_BASE = "https://api.openai.com/v1"
DEFAULT_ZHIPU_BASE = "https://open.bigmodel.cn/api/paas/v4"
DEFAULT_QWEN_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"


class OpenAIChatClient:
    """OpenAI Chat Completions（及智谱、千问 DashScope 等兼容网关）。"""

    def __init__(
        self,
        model_name: str,
        *,
        api_key: str,
        base_url: str | None = None,
        timeout_s: float = 90.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model_name = model_name
        self._api_key = api_key
        base = (base_url or DEFAULT_OPENAI_BASE).rstrip("/")
        if base.endswith("/chat/completions"):
            self._url = base
        else:
            self._url = f"{base}/chat/completions"
        self._timeout = timeout_s
        self._transport = transport

    def complete(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }
        with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
            resp = client.post(self._url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"unexpected OpenAI response: {data!r}") from exc
