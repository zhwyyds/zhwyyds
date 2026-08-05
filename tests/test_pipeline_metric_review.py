import json
from pathlib import Path

from data_governance.pipeline.metric_review import MetricReviewPipeline
from data_governance.schemas.metrics import MetricInput, MetricReviewRequest


def test_metric_review_pipeline(project_root: Path, tmp_path: Path):
    base = tmp_path / "proj"
    base.mkdir()
    (base / "config").mkdir()
    (base / "reviews" / "metric_reviews").mkdir(parents=True)
    (base / "config" / "models.csv").write_text(
        (project_root / "config" / "models.csv").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

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
    doc = MetricReviewPipeline(base_dir=base, use_mock=True).run(req)
    assert doc.items[0].final_decision.decision_type.value == "needs_revision"

    reviews = list((base / "reviews" / "metric_reviews").glob("sale_metric_review_*.json"))
    assert len(reviews) == 1
    saved = json.loads(reviews[0].read_text(encoding="utf-8"))
    assert saved["items"][0]["comparison"]["naming_score_avg"] == 4.67
