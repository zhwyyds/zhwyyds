"""导入导出 / 修饰词 CRUD / 模型 CRUD 测试（问题 3/6/11/13）。"""

from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from data_governance.api.app import create_app
from data_governance.io.catalog import load_catalog
from data_governance.io.models_store import load_models_file
from data_governance.io.modifier_rules import load_modifiers_file

ROOTS_CSV = (
    "root_id,root_cn,root_en,root_abbr,domain_code,root_type,description,source_model,review_status,created_at,updated_at\n"
    ",商户,partner,ptnr,sale,noun,商户词根,manual,pending,,\n"
    ",渠道,channel,chn,sale,noun,渠道词根,manual,pending,,\n"
)
METRICS_CSV = (
    "metric_id,metric_cn,metric_en,metric_abbr,domain_code,metric_type,caliber_desc\n"
    "M_SALE_I01,测试导入指标,test_import,tst,sale,atomic,导入测试口径\n"
)


@pytest.fixture
def api_client(mini_project: Path) -> TestClient:
    return TestClient(create_app(mini_project))


def test_export_roots(api_client: TestClient):
    r = api_client.get("/api/roots/export")
    assert r.status_code == 200
    assert "R_SALE_001" in r.text
    assert "text/csv" in r.headers["content-type"]


def test_import_roots(api_client: TestClient, mini_project: Path):
    r = api_client.post("/api/roots/import", json={"csv": ROOTS_CSV})
    assert r.status_code == 200
    body = r.json()
    assert body["created"] == 2
    roots = load_catalog(mini_project).roots
    assert any(x.root_en == "partner" and x.domain_code == "sale" for x in roots)
    assert any(x.root_en == "channel" for x in roots)


def test_import_metrics(api_client: TestClient, mini_project: Path):
    r = api_client.post("/api/metrics/import", json={"csv": METRICS_CSV})
    assert r.status_code == 200
    body = r.json()
    assert body["created"] == 1
    assert any(m.metric_id == "M_SALE_I01" for m in load_catalog(mini_project).metrics)


def test_modifier_crud(api_client: TestClient, mini_project: Path):
    # 新增
    r = api_client.post(
        "/api/modifier-rules",
        json={"modifier_cn": "上月", "modifier_en": "last_month", "modifier_type": "time", "time_scope": "prior_period"},
    )
    assert r.status_code == 200
    mid = r.json()["modifier_id"]
    assert mid  # 自动分配 T 系列

    # 更新
    r = api_client.put(f"/api/modifier-rules/{mid}", json={"description": "上月累计"})
    assert r.status_code == 200
    assert r.json()["description"] == "上月累计"

    # 删除
    r = api_client.delete(f"/api/modifier-rules/{mid}")
    assert r.status_code == 200
    ids = [m["modifier_id"] for m in load_modifiers_file(mini_project / "config" / "modifier_rules.csv")]
    assert mid not in ids


def test_model_crud(api_client: TestClient, mini_project: Path):
    r = api_client.post(
        "/api/models",
        json={"model_name": "deepseek-v3", "provider": "DeepSeek", "use_case": "root_generation", "priority": "5", "api_endpoint": "https://api.deepseek.com", "api_key_env": "DEEPSEEK_API_KEY"},
    )
    assert r.status_code == 200
    mid = r.json()["model_id"]

    r = api_client.put(f"/api/models/{mid}", json={"enabled": "false"})
    assert r.status_code == 200
    assert r.json()["enabled"] == "false"

    r = api_client.delete(f"/api/models/{mid}")
    assert r.status_code == 200
    assert all(m["model_id"] != mid for m in load_models_file(mini_project / "config" / "models.csv"))
