"""评审修订建议测试（T1：AI 产出 + 应用 API）。"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from data_governance.api.metric_services import (
    apply_metric_revision,
    merge_revision_suggestions,
)
from data_governance.io.catalog import load_catalog
from data_governance.parsing.metric_review import row_to_metric_review_fields
from data_governance.pipeline.metric_review import MetricReviewPipeline
from data_governance.schemas.metrics import MetricInput, MetricReviewRequest


@pytest.fixture
def api_client(mini_project: Path) -> TestClient:
    from data_governance.api.app import create_app

    return TestClient(create_app(mini_project))


def test_parse_revision_str_form_coerced():
    """模型把 revision 写成 JSON 字符串（而非对象）时也能规整。"""
    fields = row_to_metric_review_fields(
        {
            "metric_id": "M_SALE_001",
            "naming_score": 4,
            "caliber_score": 3,
            "root_match": True,
            "revision": '{"metric_en": "monthly_sales_amount", "summary": "补全英文名"}',
        }
    )
    assert fields["revision"]["metric_en"] == "monthly_sales_amount"


def test_parse_revision_null_skipped():
    fields = row_to_metric_review_fields(
        {
            "metric_id": "M_SALE_001",
            "naming_score": 5,
            "caliber_score": 5,
            "root_match": True,
            "revision": None,
        }
    )
    assert "revision" not in fields


def test_merge_revision_suggestions_first_nonempty():
    merged = merge_revision_suggestions(
        [
            {"model": "gpt-4o", "revision": None},
            {"model": "qwen-plus", "revision": {"metric_en": "monthly_sales_amount", "summary": "补全"}},
            {"model": "claude", "revision": {"metric_en": "monthly_sales_amt", "unit": "万元"}},
        ]
    )
    assert merged["metric_en"] == "monthly_sales_amount"  # 第一个非空
    assert merged["unit"] == "万元"
    assert merged["summary"] == "补全"


def test_apply_revision_via_pipeline_mock(mini_project: Path):
    """mock 评审（qwen 带 revision）→ 应用 metric_en/caliber_desc → 指标字段更新。"""
    from data_governance.io.metrics_csv import upsert_metric

    # 造一条 M_SALE_001 评审（走 pipeline mock）
    req = MetricReviewRequest(
        domain="sale",
        metrics=[
            MetricInput(
                metric_id="M_SALE_001",
                metric_cn="月度销售额",
                metric_en="monthly_sales_amt",
                caliber_desc="自然月内已完成订单的销售总金额，不含退款",
                root_ids=["R_SALE_001", "R_TIME_001"],
                unit="元",
                frequency="月",
            )
        ],
    )
    doc = MetricReviewPipeline(base_dir=mini_project, use_mock=True).run(req)

    # 先重置指标字段为旧值（模拟评审前的定义）
    upsert_metric(mini_project, "M_SALE_001", {"metric_en": "monthly_sales_amt"})

    result = apply_metric_revision(
        mini_project,
        "M_SALE_001",
        doc.review_id,
        ["metric_en", "caliber_desc"],
        checked_by="tester",
    )
    assert result["applied_fields"] == ["metric_en", "caliber_desc"]

    catalog = load_catalog(mini_project)
    m = next(x for x in catalog.metrics if x.metric_id == "M_SALE_001")
    assert m.metric_en == "monthly_sales_amount"  # qwen 的修订建议
    assert "不含增值税" in m.caliber_desc


def test_apply_revision_unknown_review_400(mini_project: Path, api_client: TestClient):
    r = api_client.post(
        "/api/metrics/M_SALE_001/review/NOT_EXIST/apply-revision",
        json={"fields": ["metric_en"]},
    )
    assert r.status_code == 400
    assert "review not found" in r.json()["detail"]


def test_apply_revision_api_flow(mini_project: Path, api_client: TestClient):
    """API 全流程：评审 → 应用修订 → 指标更新。"""
    r = api_client.post("/api/metrics/M_SALE_001/review")
    assert r.status_code == 200, r.text
    review_id = r.json()["review_id"]

    r2 = api_client.post(
        f"/api/metrics/M_SALE_001/review/{review_id}/apply-revision",
        json={"fields": ["metric_en"], "checked_by": "tester"},
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert "metric_en" in body["applied_fields"]

    # 落到 CSV
    catalog = load_catalog(mini_project)
    m = next(x for x in catalog.metrics if x.metric_id == "M_SALE_001")
    assert m.metric_en == "monthly_sales_amount"
