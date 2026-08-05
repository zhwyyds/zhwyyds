"""suggest 降级容错测试（G6）。

DeepSeek 偶发返回 JSON 但 metric_en 字段缺失/空——不应 500，应返回 200 + 警告让用户手填。
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


class _FakeClient:
    """模拟 OpenAIChatClient：complete 返回 metric_en 故意为空的 JSON（模拟 DeepSeek 漂移）。"""

    model_name = "fake-deepseek"

    def __init__(self, model_name: str = "fake-deepseek") -> None:
        self.model_name = model_name

    def complete(self, prompt: str) -> str:
        return (
            '{"metric_abbr":"amt","caliber_desc":"统计金额",'
            '"unit":"元","frequency":"月","suggestions":[],"suggested_roots":[]}'
        )


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch, mini_project: Path) -> TestClient:
    """patch factory.build_live_clients 返回 fake 客户端 + resolve_use_mock 走 live。"""
    from data_governance.api.app import create_app
    from data_governance.llm import factory as llm_factory

    monkeypatch.setattr(llm_factory, "build_live_clients", lambda configs: [_FakeClient()])
    monkeypatch.setenv("DATA_GOV_LLM_MODE", "live")
    return TestClient(create_app(mini_project))


def test_suggest_degrades_when_metric_en_empty(api_client: TestClient):
    """DeepSeek 返回无 metric_en → 200 + 警告 + metric_en=空，前端可让用户手填。"""
    r = api_client.post(
        "/api/metrics/suggest",
        json={"metric_cn": "金额", "domain_code": "sale"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["metric_en"] == ""
    assert "手动填写" in body.get("metric_en_warning", "")
    # 其他字段正常返回
    assert body["metric_abbr"] == "amt"
    assert body["caliber_desc"] == "统计金额"
    assert body["unit"] == "元"
    assert body["suggested_roots"] == []
