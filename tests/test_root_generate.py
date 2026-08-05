"""词根 AI 生成测试（T3 / 问题 7）。"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from data_governance.io.catalog import load_catalog
from data_governance.pipeline.root_generation import RootGenerationPipeline
from data_governance.schemas.roots import RootGenerationRequest, TermInput


@pytest.fixture
def api_client(mini_project: Path) -> TestClient:
    from data_governance.api.app import create_app

    return TestClient(create_app(mini_project))


def test_root_generate_api_mock(mini_project: Path, api_client: TestClient):
    """POST /api/roots/generate：mock 模式返回评审结果，不写库。"""
    r = api_client.post(
        "/api/roots/generate",
        json={"domain": "sale", "terms": [{"cn_term": "客户", "context": "销售域核心金额词根"}]},
    )
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["review_id"].startswith("RR_")
    assert len(doc["items"]) == 1
    it = doc["items"][0]
    assert it["cn_term"] == "客户"
    assert it["model_results"], "应有模型生成结果"
    assert it["final_decision"]["root_en"]

    # 不写库
    catalog = load_catalog(mini_project)
    assert all(rt.root_cn != "客户" for rt in catalog.roots)


def test_root_generate_commit_flow(mini_project: Path, api_client: TestClient):
    """生成 → 确认入库 → 词根 CSV 出现。"""
    r = api_client.post(
        "/api/roots/generate",
        json={"domain": "sale", "terms": [{"cn_term": "客户"}]},
    )
    doc = r.json()
    review_id = doc["review_id"]
    item = doc["items"][0]
    assert item["auto_approved"], "mock 3 模型一致应自动通过"

    r2 = api_client.post(
        "/api/roots/generate/commit",
        json={"review_id": review_id, "cn_terms": ["客户"]},
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["created"] == ["客户"]

    catalog = load_catalog(mini_project)
    created = next((rt for rt in catalog.roots if rt.root_cn == "客户"), None)
    assert created is not None
    assert created.domain_code == "sale"
    assert created.root_en  # AI 生成的英文名


def test_root_generate_commit_empty_terms_writes_all(mini_project: Path, api_client: TestClient):
    """cn_terms 为空 → 全部 auto_approved 词根入库。"""
    r = api_client.post(
        "/api/roots/generate",
        json={"domain": "sale", "terms": [{"cn_term": "客户"}, {"cn_term": "商品"}]},
    )
    doc = r.json()
    r2 = api_client.post(
        "/api/roots/generate/commit",
        json={"review_id": doc["review_id"], "cn_terms": []},
    )
    body = r2.json()
    assert len(body["created"]) >= 1


def test_root_pipeline_single_model_threshold(mini_project: Path):
    """单模型门槛已放宽（<2 → <1），pipeline 至少不因门槛报错。"""
    req = RootGenerationRequest(
        domain="sale", terms=[TermInput(cn_term="客户", context="")]
    )
    doc = RootGenerationPipeline(base_dir=mini_project, use_mock=True).run(req)
    assert len(doc.items) == 1


def test_root_generate_reuses_existing_root(mini_project: Path, api_client: TestClient):
    """语义归并：输入词根命中已有词根 → 返回 reuse 标记（前端置为不可勾选，不提交）。"""
    r = api_client.post(
        "/api/roots/generate",
        json={"domain": "sale", "terms": [{"cn_term": "订单"}]},
    )
    assert r.status_code == 200, r.text
    item = r.json()["items"][0]
    assert item["reused_root_id"] == "R_SALE_001"
    assert item["final_decision"]["root_en"] == "order"

    # reuse 条目不落盘 review，前端也不会提交（disabled）；直接 commit 空勾选 → 404 合理
    r2 = api_client.post(
        "/api/roots/generate/commit",
        json={"review_id": r.json()["review_id"], "cn_terms": []},
    )
    assert r2.status_code == 404
