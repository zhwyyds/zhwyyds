from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from data_governance.api.app import create_app


@pytest.fixture
def api_client(mini_project: Path) -> TestClient:
    app = create_app(mini_project)
    return TestClient(app)


def test_health_and_catalog(api_client: TestClient):
    r = api_client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    r = api_client.get("/api/llm/status")
    assert r.status_code == 200
    body = r.json()
    assert "mode" in body and "use_mock" in body
    assert body["use_mock"] is True

    r = api_client.get("/api/metrics")
    assert r.status_code == 200
    assert len(r.json()) >= 1

    r = api_client.get("/api/roots?domain=sale")
    assert r.status_code == 200
    assert all(row["domain_code"] == "sale" for row in r.json())


def test_metric_tree(api_client: TestClient):
    r = api_client.get("/api/metric-tree")
    assert r.status_code == 200
    body = r.json()
    assert "nodes" in body
    assert "metrics_by_node" in body
    assert isinstance(body["nodes"], list)


def test_metric_upsert(api_client: TestClient):
    r = api_client.get("/api/metrics")
    mid = r.json()[0]["metric_id"]
    r = api_client.put(
        f"/api/metrics/{mid}",
        json={"caliber_desc": "测试更新口径", "owner": "测试部"},
    )
    assert r.status_code == 200
    assert r.json()["caliber_desc"] == "测试更新口径"
    r = api_client.get("/api/metrics")
    row = next(x for x in r.json() if x["metric_id"] == mid)
    assert row["owner"] == "测试部"


def test_metric_stats(api_client: TestClient):
    r = api_client.get("/api/metrics/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert "pending_review" in body
    assert "published" in body


def test_metric_review_endpoint(api_client: TestClient):
    r = api_client.get("/api/metrics")
    mid = r.json()[0]["metric_id"]
    r = api_client.post(f"/api/metrics/{mid}/review")
    assert r.status_code == 200
    body = r.json()
    assert body.get("review_type") == "metric_review"
    assert body.get("items")


def test_metric_offline_and_objection(api_client: TestClient):
    r = api_client.get("/api/metrics")
    mid = r.json()[0]["metric_id"]
    r = api_client.put(
        f"/api/metrics/{mid}",
        json={"review_status": "offline", "offline_reason": "duplicate", "offline_note": "test"},
    )
    assert r.status_code == 200
    assert r.json()["review_status"] == "offline"
    assert r.json()["offline_reason"] == "duplicate"
    r = api_client.post(f"/api/metrics/{mid}/review")
    assert r.status_code == 200
    r = api_client.get(f"/api/metrics/{mid}/review/latest")
    assert r.status_code == 200
    assert r.json()["item"]["metric_id"] == mid
    r = api_client.put(
        f"/api/metrics/{mid}",
        json={"objection_status": "open", "objection_note": "caliber_desc：口径有误", "review_status": "approved"},
    )
    assert r.status_code == 200
    assert r.json()["objection_status"] == "open"


def test_metric_review_mock_fallback_for_unknown(api_client: TestClient):
    """不在 mock fixture 里的指标评审应返回中性结果而非 404（问题修复回归保护）。"""
    r = api_client.post(
        "/api/metrics",
        json={"metric_id": "M_SALE_999", "metric_cn": "测试指标", "metric_en": "test_metric", "domain_code": "sale"},
    )
    assert r.status_code == 200
    r = api_client.post("/api/metrics/M_SALE_999/review")
    assert r.status_code == 200
    assert r.json().get("items")


def test_lineage_and_modifiers(project_root: Path):
    if not (project_root / "lineage" / "sale_lineage.json").is_file():
        pytest.skip("sale_lineage.json not in repo")
    client = TestClient(create_app(project_root))
    r = client.get("/api/lineage?domain=sale")
    assert r.status_code == 200
    assert r.json()["domain"] == "sale"
    r = client.get("/api/modifier-rules")
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_metrics_export(api_client: TestClient):
    r = api_client.get("/api/metrics/export")
    assert r.status_code == 200
    assert "metric_id" in r.text


def test_acceptance_live(api_client: TestClient):
    r = api_client.get("/api/acceptance?refresh=true")
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "live"
    assert "total_points" in body
    assert "dimensions" in body
