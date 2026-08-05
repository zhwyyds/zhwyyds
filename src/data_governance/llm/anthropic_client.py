from __future__ import annotations

from typing import Any

import httpx

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicMessagesClient:
    def __init__(
        self,
        model_name: str,
        *,
        api_key: str,
        timeout_s: float = 90.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model_name = model_name
        self._api_key = api_key
        self._timeout = timeout_s
        self._transport = transport

    def complete(self, prompt: str) -> str:
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "model": self.model_name,
            "max_tokens": 4096,
            "temperature": 0.2,
            "messages": [{"role": "user", "content": prompt}],
        }
        with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
            resp = client.post(ANTHROPIC_URL, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
        try:
            blocks = data["content"]
            parts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
            return "".join(parts)
        except (KeyError, TypeError) as exc:
            raise RuntimeError(f"unexpected Anthropic response: {data!r}") from exc
