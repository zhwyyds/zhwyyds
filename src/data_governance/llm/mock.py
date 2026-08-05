from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from data_governance.schemas.roots import TermInput


class MockLLMClient:
    """Returns fixed JSON arrays for integration tests."""

    def __init__(
        self,
        model_name: str,
        *,
        responses_by_term: dict[str, dict] | None = None,
        responder: Callable[[str, list[Any]], list[dict]] | None = None,
    ) -> None:
        self.model_name = model_name
        self._responses_by_term = responses_by_term or {}
        self._responder = responder

    def complete(self, prompt: str) -> str:
        del prompt
        if self._responder is not None:
            raise RuntimeError("MockLLMClient with responder must use complete_batch")
        items = list(self._responses_by_term.values())
        return json.dumps(items, ensure_ascii=False)

    def complete_for_batch(self, batch: list[Any]) -> str:
        if self._responder is not None:
            return json.dumps(self._responder(self.model_name, batch), ensure_ascii=False)
        out = []
        for term in batch:
            cn = term.cn_term if hasattr(term, "cn_term") else term
            if cn not in self._responses_by_term:
                raise KeyError(f"no mock response for cn_term={cn!r}")
            row = dict(self._responses_by_term[cn])
            row.setdefault("cn_term", cn)
            out.append(row)
        return json.dumps(out, ensure_ascii=False)

    def complete_for_terms(self, terms: list[TermInput]) -> str:
        return self.complete_for_batch(terms)


def run_models_parallel(
    clients: list[MockLLMClient],
    batch: list[Any],
) -> list[tuple[str, str]]:
    from data_governance.llm.parallel import run_models_parallel_mock

    return run_models_parallel_mock(clients, batch)


def default_customer_fixture() -> dict[str, dict[str, dict[str, str]]]:
    """model_name -> cn_term -> fields (文档 §2.5 客户示例)."""
    base = {
        "root_en": "customer",
        "root_type": "noun",
    }
    return {
        "gpt-4o": {
            "客户": {
                **base,
                "root_abbr": "cust",
                "description": "客户的统称",
            }
        },
        "claude-3.5-sonnet": {
            "客户": {
                **base,
                "root_abbr": "cust",
                "description": "消费者客户",
            }
        },
        "qwen-plus": {
            "客户": {
                **base,
                "root_abbr": "cst",
                "description": "客户",
            }
        },
    }


def clients_from_fixture(
    model_names: list[str],
    fixture: dict[str, dict[str, dict[str, str]]],
) -> list[MockLLMClient]:
    clients: list[MockLLMClient] = []

    def make_responder(name: str) -> MockLLMClient:
        # 未配置 fixture 的模型（如后加的 DeepSeek）复用第一个模型的响应
        fallback = next(iter(fixture.values()), {})
        per_term = fixture.get(name) or fallback

        def responder(model: str, terms: list[TermInput]) -> list[dict]:
            del model
            out = []
            for t in terms:
                if t.cn_term not in per_term:
                    raise KeyError(f"{name}: no data for {t.cn_term!r}")
                row = dict(per_term[t.cn_term])
                row["cn_term"] = t.cn_term
                out.append(row)
            return out

        return MockLLMClient(name, responder=responder)

    # mock 只对 fixture 定义的模型出稿；若启用模型与 fixture 无交集，回退用 fixture 全部模型
    names = [n for n in model_names if n in fixture] or list(fixture.keys())
    for name in names:
        clients.append(make_responder(name))
    return clients
