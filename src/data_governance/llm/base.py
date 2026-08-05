from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    model_name: str

    def complete(self, prompt: str) -> str: ...
