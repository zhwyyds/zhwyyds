"""口径助手联动测试（IT2-6）：发布门禁 + 存量补全 + 评分升级。"""

from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from data_governance.api.app import create_app
from data_governance.caliber.draft import draft_caliber, persist_draft
from data_governance.caliber.review import backfill_calibers
from data_governance.io.catalog import load_catalog
from data_governance.release.service import publish_domain
from data_governance.scoring.engine import score_metric


def _draft_metric(mini_project: Path, metric_id: str = "M_SALE_001") -> None:
    catalog = load_catalog(mini_project)
    m = next(x for x in catalog.metrics if x.metric_id == metric_id)
    result = draft_caliber(m, base_dir=mini_project, use_mock=True)
    persist_draft(mini_project, metric_id, result)


def test_publish_blocked_by_pending_caliber(mini_project: Path):
    _draft_metric(mini_project)  # status -> pending
    with pytest.raises(ValueError, match="口径未核查"):
        publish_domain(mini_project, "sale")


def test_publish_after_approve(mini_project: Path):
    _draft_metric(mini_project)
    from data_governance.caliber.review import approve_caliber

    approve_caliber(mini_project, "M_SALE_001")
    record = publish_domain(mini_project, "sale")
    assert record.version == 1


def test_publish_unaffected_by_legacy(mini_project: Path):
    # 存量指标 caliber_status="" 不受门禁影响
    record = publish_domain(mini_project, "sale")
    assert record.version == 1


def test_backfill_drafts_missing(mini_project: Path):
    # mini_project 有 1 个指标未起草
    result = backfill_calibers(mini_project, dry_run=False)
    assert result["drafted"] == 1
    m = next(x for x in load_catalog(mini_project).metrics if x.metric_id == "M_SALE_001")
    assert m.caliber_status == "pending"

    # 再跑一次：已起草，drafted=0
    again = backfill_calibers(mini_project, dry_run=False)
    assert again["drafted"] == 0


def test_backfill_dry_run_no_write(mini_project: Path):
    result = backfill_calibers(mini_project, dry_run=True)
    assert result["drafted"] == 1
    assert result["dry_run"] is True
    m = next(x for x in load_catalog(mini_project).metrics if x.metric_id == "M_SALE_001")
    assert m.caliber_status == ""


def test_scoring_uses_structured_caliber(mini_project: Path):
    """结构化口径字段优先：起草后 caliber 维度使用 caliber_business/formula/period。"""
    _draft_metric(mini_project)
    catalog = load_catalog(mini_project)
    m = next(x for x in catalog.metrics if x.metric_id == "M_SALE_001")
    result = score_metric(m, catalog, mini_project)
    caliber_dim = next(d for d in result.dimensions if d.dim_code == "caliber")
    items = {i.item: i for i in caliber_dim.items}
    assert items["业务定义"].status == "pass"
    assert items["计算公式"].status == "pass"  # caliber_formula 已由 mock 起草
    assert items["统计周期"].status == "pass"


@pytest.fixture
def api_client(mini_project: Path) -> TestClient:
    return TestClient(create_app(mini_project))


def test_api_backfill(api_client: TestClient, mini_project: Path):
    r = api_client.post("/api/caliber/backfill", json={"domain": "sale"})
    assert r.status_code == 200
    assert r.json()["drafted"] == 1
    assert len(api_client.get("/api/caliber/pending").json()) == 1
