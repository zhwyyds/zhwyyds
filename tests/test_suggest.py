"""新增指标 AI 辅助 suggest 测试（问题 2 修复）。"""

from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from data_governance.api.app import create_app


@pytest.fixture
def api_client(mini_project: Path) -> TestClient:
    return TestClient(create_app(mini_project))


def test_suggest_requires_cn(api_client: TestClient):
    r = api_client.post("/api/metrics/suggest", json={"metric_cn": ""})
    assert r.status_code == 400


def test_suggest_reuses_similar_metric(api_client: TestClient):
    # mini_project 有 M_SALE_001（月度销售额）；suggest 同中文名 → 复用
    r = api_client.post("/api/metrics/suggest", json={"metric_cn": "月度销售额", "domain_code": "sale"})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "similar_metric"
    assert body["metric_en"] == "monthly_sales_amt"


def test_suggest_rule_hint(api_client: TestClient):
    # "订单金额" 不在指标库 → 词根提示（订单 order 命中）
    r = api_client.post("/api/metrics/suggest", json={"metric_cn": "订单金额", "domain_code": "sale"})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "rule_hint"
    assert "order" in body["metric_en"]
