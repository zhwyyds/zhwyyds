"""域级治理看板测试（IT3-2）。"""

from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from data_governance.api.app import create_app
from data_governance.dashboard import domain_dashboard
from data_governance.release.service import publish_domain
from data_governance.scoring.store import score_and_persist


def test_dashboard_basic(mini_project: Path):
    rows = domain_dashboard(mini_project)
    sale = next(r for r in rows if r["domain"] == "sale")
    assert sale["roots_count"] == 1  # R_TIME_001 属于 base 域
    assert sale["metrics_count"] == 1
    assert sale["score_avg"] is None  # 未评分
    assert sale["lineage_ok"] is False
    assert sale["caliber_pending"] == 0
    assert sale["latest_version"] is None


def test_dashboard_with_score_and_release(mini_project: Path):
    score_and_persist(mini_project, "M_SALE_001", trigger="test")
    publish_domain(mini_project, "sale", note="首版")

    rows = domain_dashboard(mini_project)
    sale = next(r for r in rows if r["domain"] == "sale")
    assert sale["score_avg"] is not None
    assert sum(sale["grade_dist"].values()) == 1
    assert sale["latest_version"] == "v1"


@pytest.fixture
def api_client(mini_project: Path) -> TestClient:
    return TestClient(create_app(mini_project))


def test_api_dashboard(api_client: TestClient):
    r = api_client.get("/api/dashboard/domains")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) >= 1  # 至少 sale 域
    keys = {"domain", "roots_count", "metrics_count", "score_avg", "grade_dist", "lineage_ok", "caliber_pending"}
    assert keys <= set(rows[0].keys())
