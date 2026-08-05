"""血缘上传 API 测试（IT2-3）。"""

import json
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from data_governance.api.app import create_app
from data_governance.io.lineage_loader import load_domain_lineage

VALID_LINEAGE = {
    "domain": "sale",
    "domain_name": "交易",
    "version": "1.0.0",
    "lineages": [
        {
            "lineage_id": "LN_SALE_001",
            "target_table": "dwd_sale_order_df",
            "metric_ids": ["M_SALE_001"],
            "source_tables": [{"table_name": "ods_sale_order_info"}],
        }
    ],
}


@pytest.fixture
def api_client(mini_project: Path) -> TestClient:
    return TestClient(create_app(mini_project))


def test_upload_lineage_writes_file(api_client: TestClient, mini_project: Path):
    r = api_client.post("/api/lineage/upload", json=VALID_LINEAGE)
    assert r.status_code == 200
    body = r.json()
    assert body["domain"] == "sale"
    assert body["lineages"] == 1

    saved = load_domain_lineage(mini_project, "sale")
    assert saved is not None
    assert saved["lineages"][0]["lineage_id"] == "LN_SALE_001"


def test_upload_lineage_rejects_bad_structure(api_client: TestClient):
    r = api_client.post("/api/lineage/upload", json={"domain": "sale", "lineages": [{"foo": 1}]})
    assert r.status_code == 400
    assert "lineage_id" in r.json()["detail"]


def test_upload_lineage_requires_domain(api_client: TestClient):
    r = api_client.post("/api/lineage/upload", json={"lineages": []})
    assert r.status_code == 400
    assert "domain" in r.json()["detail"]


def test_upload_lineage_overwrites_existing(api_client: TestClient, mini_project: Path):
    r1 = api_client.post("/api/lineage/upload", json=VALID_LINEAGE)
    assert r1.status_code == 200
    updated = json.loads(json.dumps(VALID_LINEAGE))
    updated["lineages"][0]["target_table"] = "dwd_sale_order_df_v2"
    r2 = api_client.post("/api/lineage/upload", json=updated)
    assert r2.status_code == 200
    assert load_domain_lineage(mini_project, "sale")["lineages"][0]["target_table"] == "dwd_sale_order_df_v2"
