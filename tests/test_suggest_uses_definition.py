"""验证：suggest 必须基于业务定义/计算公式生成（口语化中文名不作为唯一依据）。

用户核心诉求：不能仅凭中文名生成，prompt 必须携带业务定义/公式，
并强制 AI 以定义/公式为准理解语义（prompt 语义判定规则 0）。
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


class _CaptureClient:
    """记录传给 LLM 的 prompt，返回合法 suggest JSON。"""

    model_name = "capture"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return (
            '{"metric_en":"monthly_rent_amount",'
            '"caliber_desc":"自然月应收租金","unit":"元","frequency":"月",'
            '"suggested_roots":[]}'
        )


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch, mini_project: Path) -> TestClient:
    from data_governance.api.app import create_app
    from data_governance.llm import factory as llm_factory

    client = _CaptureClient()
    monkeypatch.setattr(llm_factory, "build_live_clients", lambda configs: [client])
    monkeypatch.setenv("DATA_GOV_LLM_MODE", "live")
    app = create_app(mini_project)
    app.state.capture_client = client
    return TestClient(app)


def test_suggest_prompt_contains_business_definition(api_client: TestClient):
    """带业务定义/公式时：prompt 必须包含定义、公式、规则0，且中文名不作为唯一依据。"""
    r = api_client.post(
        "/api/metrics/suggest",
        json={
            "metric_cn": "收的租",  # 口语化名称
            "domain_code": "sale",
            "caliber_desc": "按租赁合同约定，每月应收的租金金额，不含押金和物业费",
            "formula": "SUM(合同月租金) WHERE 合同生效",
            "unit": "元",
            "frequency": "月",
        },
    )
    assert r.status_code == 200, r.text
    client = api_client.app.state.capture_client
    prompt = client.prompts[-1]
    # 关键断言：定义/公式进入 prompt
    assert "按租赁合同约定" in prompt, "业务定义未传入 prompt"
    assert "SUM(合同月租金)" in prompt, "计算公式未传入 prompt"
    # 规则 0：名称口语化必须以定义为准
    assert "口语化" in prompt, "缺少语义判定规则 0（以定义为准）"
    assert "业务定义/描述" in prompt or "业务定义/计算公式" in prompt


def test_suggest_prompt_without_definition_still_has_rule0(api_client: TestClient):
    """无定义时也要保留规则 0（提示用户以定义为准）。"""
    r = api_client.post(
        "/api/metrics/suggest",
        json={"metric_cn": "收的租", "domain_code": "sale"},
    )
    assert r.status_code == 200, r.text
    client = api_client.app.state.capture_client
    prompt = client.prompts[-1]
    assert "口语化" in prompt, "缺少规则 0"
