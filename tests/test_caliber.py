"""口径助手起草链路测试（IT2-4）。"""

from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from data_governance.api.app import create_app
from data_governance.caliber.draft import (
    build_prompt,
    draft_caliber,
    merge_drafts,
    parse_response,
    persist_draft,
)
from data_governance.io.catalog import load_catalog


@pytest.fixture
def api_client(mini_project: Path) -> TestClient:
    return TestClient(create_app(mini_project))


def test_parse_response_extracts_json_block():
    text = "好的，以下是结果：\n{\"caliber_business\": \"测试\", \"caliber_period\": \"月\"}\n结束"
    data = parse_response(text)
    assert data["caliber_business"] == "测试"


def test_parse_response_returns_empty_on_garbage():
    assert parse_response("这不是 JSON") == {}


def test_build_prompt_contains_metric_info(mini_project: Path):
    catalog = load_catalog(mini_project)
    m = next(x for x in catalog.metrics if x.metric_id == "M_SALE_001")
    prompt = build_prompt(m)
    assert m.metric_cn in prompt
    assert "caliber_business" in prompt


def test_draft_caliber_mock_produces_draft(mini_project: Path):
    catalog = load_catalog(mini_project)
    m = next(x for x in catalog.metrics if x.metric_id == "M_SALE_001")
    result = draft_caliber(m, base_dir=mini_project, use_mock=True)
    assert result.metric_id == "M_SALE_001"
    assert result.draft.get("caliber_business")
    assert result.draft.get("caliber_period")
    assert isinstance(result.diff_summary, list)
    assert isinstance(result.high_risk, bool)
    assert len(result.by_model) >= 1  # 单模型模式（仅 DeepSeek 启用时也成立）
    assert "consensus" in result.ai_by or "divergent" in result.ai_by


def test_persist_draft_writes_fields(mini_project: Path):
    catalog = load_catalog(mini_project)
    m = next(x for x in catalog.metrics if x.metric_id == "M_SALE_001")
    result = draft_caliber(m, base_dir=mini_project, use_mock=True)
    persist_draft(mini_project, m.metric_id, result)

    reloaded = load_catalog(mini_project)
    m2 = next(x for x in reloaded.metrics if x.metric_id == "M_SALE_001")
    assert m2.caliber_status == "pending"
    assert m2.caliber_business
    assert m2.caliber_ai_by


def test_merge_drafts_consensus_and_divergent():
    drafts = [
        ("gpt-4o", {"caliber_business": "A", "caliber_period": "月", "caliber_boundary": "X"}),
        ("claude", {"caliber_business": "A", "caliber_period": "月", "caliber_boundary": "Y"}),
        ("qwen", {"caliber_business": "B", "caliber_period": "月", "caliber_boundary": "Y"}),
    ]
    merged, diff_summary, high_risk = merge_drafts(drafts)
    assert merged["caliber_business"] == "A"
    assert merged["caliber_period"] == "月"
    fields = {d["field"] for d in diff_summary}
    assert "caliber_business" in fields  # business 分歧 → 必然 high_risk
    assert high_risk is True


def test_api_caliber_draft(api_client: TestClient, mini_project: Path):
    r = api_client.post("/api/metrics/M_SALE_001/caliber/draft")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending"
    assert body["caliber"]["caliber_business"]

    reloaded = load_catalog(mini_project)
    m = next(x for x in reloaded.metrics if x.metric_id == "M_SALE_001")
    assert m.caliber_status == "pending"
    assert m.caliber_business


def test_api_caliber_draft_not_found(api_client: TestClient):
    r = api_client.post("/api/metrics/M_NO_SUCH/caliber/draft")
    assert r.status_code == 404
