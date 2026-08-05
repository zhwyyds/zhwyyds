"""口径核查流测试（IT2-5）。"""

from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from data_governance.api.app import create_app
from data_governance.caliber.draft import draft_caliber, persist_draft
from data_governance.caliber.review import (
    approve_caliber,
    pending_queue,
    reject_caliber,
    update_caliber,
)
from data_governance.io.catalog import load_catalog
from data_governance.scoring.store import load_score


def _drafted(mini_project: Path) -> Path:
    catalog = load_catalog(mini_project)
    m = next(x for x in catalog.metrics if x.metric_id == "M_SALE_001")
    result = draft_caliber(m, base_dir=mini_project, use_mock=True)
    persist_draft(mini_project, m.metric_id, result)
    return mini_project


def test_pending_queue_empty_before_draft(mini_project: Path):
    assert pending_queue(mini_project) == []


def test_pending_queue_after_draft(mini_project: Path):
    base = _drafted(mini_project)
    queue = pending_queue(base)
    assert len(queue) == 1
    item = queue[0]
    assert item["metric_id"] == "M_SALE_001"
    assert item["caliber_status"] == "pending"
    assert item["caliber"]["caliber_business"]


def test_approve_sets_status_and_rescores(mini_project: Path):
    base = _drafted(mini_project)
    result = approve_caliber(base, "M_SALE_001", checked_by="tester")
    assert result["status"] == "approved"

    m = next(x for x in load_catalog(base).metrics if x.metric_id == "M_SALE_001")
    assert m.caliber_status == "approved"
    assert m.caliber_checked_by == "tester"
    assert m.caliber_checked_at
    # 批准后已生成评分
    assert load_score(base, "M_SALE_001") is not None


def test_reject_sets_status_with_reason(mini_project: Path):
    base = _drafted(mini_project)
    result = reject_caliber(base, "M_SALE_001", "含税口径需财务确认", checked_by="tester")
    assert result["status"] == "rejected"

    m = next(x for x in load_catalog(base).metrics if x.metric_id == "M_SALE_001")
    assert m.caliber_status == "rejected"
    assert "财务" in m.caliber_reject_reason
    # 打回后仍在待核查队列（可重新起草）
    assert any(i["metric_id"] == "M_SALE_001" for i in pending_queue(base))


def test_update_marks_edited(mini_project: Path):
    base = _drafted(mini_project)
    result = update_caliber(base, "M_SALE_001", {"caliber_business": "人工修正后的口径"}, checked_by="tester")
    assert result["status"] == "edited"

    m = next(x for x in load_catalog(base).metrics if x.metric_id == "M_SALE_001")
    assert m.caliber_status == "edited"
    assert m.caliber_business == "人工修正后的口径"


def test_update_rejects_unknown_fields(mini_project: Path):
    base = _drafted(mini_project)
    with pytest.raises(ValueError):
        update_caliber(base, "M_SALE_001", {"foo": "bar"})


@pytest.fixture
def api_client(mini_project: Path) -> TestClient:
    return TestClient(create_app(mini_project))


def test_api_approve_flow(api_client: TestClient, mini_project: Path):
    r = api_client.post("/api/metrics/M_SALE_001/caliber/draft")
    assert r.status_code == 200

    r = api_client.get("/api/caliber/pending")
    assert len(r.json()) == 1

    r = api_client.post("/api/metrics/M_SALE_001/caliber/approve", json={"checked_by": "tester"})
    assert r.status_code == 200
    assert r.json()["status"] == "approved"

    r = api_client.get("/api/caliber/pending")
    assert r.json() == []


def test_api_reject_requires_reason(api_client: TestClient, mini_project: Path):
    api_client.post("/api/metrics/M_SALE_001/caliber/draft")
    r = api_client.post("/api/metrics/M_SALE_001/caliber/reject", json={"reason": ""})
    assert r.status_code == 400
