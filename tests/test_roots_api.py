"""词根写 API 测试（IT2-2）。"""

from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from data_governance.api.app import create_app
from data_governance.io.catalog import load_catalog


@pytest.fixture
def api_client(mini_project: Path) -> TestClient:
    return TestClient(create_app(mini_project))


def test_create_root_assigns_id(api_client: TestClient):
    r = api_client.post(
        "/api/roots",
        json={
            "root_cn": "金额",
            "root_en": "amount",
            "root_abbr": "amt",
            "domain_code": "sale",
            "root_type": "noun",
            "description": "金额词根",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["root_id"].startswith("R_SALE_")
    assert body["root_cn"] == "金额"
    assert body["review_status"] == "pending"


def test_create_root_persisted(api_client: TestClient, mini_project: Path):
    api_client.post(
        "/api/roots",
        json={"root_cn": "金额", "root_en": "amount", "domain_code": "sale"},
    )
    roots = load_catalog(mini_project).roots
    assert any(r.root_en == "amount" and r.domain_code == "sale" for r in roots)


def test_create_root_duplicate_en_rejected(api_client: TestClient):
    # mini_project 已有 sale 词根 R_SALE_001/order
    r = api_client.post(
        "/api/roots",
        json={"root_cn": "订单2", "root_en": "order", "domain_code": "sale"},
    )
    assert r.status_code == 400
    assert "already exists" in r.json()["detail"]


def test_create_root_unknown_domain_rejected(api_client: TestClient):
    r = api_client.post(
        "/api/roots",
        json={"root_cn": "测试", "root_en": "test_root", "domain_code": "nope"},
    )
    assert r.status_code == 400


def test_update_root(api_client: TestClient):
    r = api_client.put("/api/roots/R_SALE_001", json={"description": "订单词根（更新）"})
    assert r.status_code == 200
    assert r.json()["description"] == "订单词根（更新）"

    r = api_client.get("/api/roots?domain=sale")
    row = next(x for x in r.json() if x["root_id"] == "R_SALE_001")
    assert row["description"] == "订单词根（更新）"


def test_update_root_not_found(api_client: TestClient):
    r = api_client.put("/api/roots/R_NO_SUCH", json={"description": "x"})
    assert r.status_code == 404


def test_create_root_with_synonyms(mini_project: Path, api_client: TestClient):
    """POST /api/roots 支持 synonyms 字段写入（G1 回归保护）。"""
    r = api_client.post(
        "/api/roots",
        json={
            "root_cn": "商户",
            "root_en": "merchant",
            "root_abbr": "mcht",
            "root_type": "noun",
            "domain_code": "sale",
            "description": "商户词根",
            "synonyms": "商家|租户",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["synonyms"] == "商家|租户"
    catalog = load_catalog(mini_project)
    hit = next(x for x in catalog.roots if x.root_id == body["root_id"])
    assert hit.synonyms == "商家|租户"


def test_roots_suggest_reuses_existing(mini_project: Path, api_client: TestClient):
    """POST /api/roots/suggest：命中已有词根（含同义词）→ 返回 reuse，不调 LLM。"""
    r = api_client.post(
        "/api/roots/suggest",
        json={"root_cn": "订单", "domain": "sale"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["root_en"] == "order"
    assert body["reused_root_id"] == "R_SALE_001"


def test_roots_suggest_unknown_mock_warning(mini_project: Path, api_client: TestClient):
    """mock 模式未知词根 → 200 + warning，不 500。"""
    r = api_client.post(
        "/api/roots/suggest",
        json={"root_cn": "机器人", "domain": "sale"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["root_en"] == ""
    assert "mock" in body.get("warning", "")
