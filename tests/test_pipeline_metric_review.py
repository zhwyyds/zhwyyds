import json
from pathlib import Path

from data_governance.parsing.metric_review import (
    parse_metric_review_response,
    row_to_metric_review_fields,
)
from data_governance.pipeline.metric_review import MetricReviewPipeline
from data_governance.schemas.metrics import MetricInput, MetricReviewRequest, ModelMetricReview


def test_metric_review_pipeline(project_root: Path, tmp_path: Path):
    base = tmp_path / "proj"
    base.mkdir()
    (base / "config").mkdir()
    (base / "reviews" / "metric_reviews").mkdir(parents=True)
    # 自包含固定模型配置：仅启用 mock fixture 覆盖的 3 路模型（gpt-4o/claude-3.5-sonnet/qwen-plus），
    # 避免断言 4.67 依赖运行时 config/models.csv（任何 enabled 开关变化都会改变平均分）。
    (base / "config" / "models.csv").write_text(
        "model_id,model_name,provider,use_case,priority,enabled,api_endpoint,api_key_env,remark\n"
        "1,gpt-4o,OpenAI,metric_review,1,true,,OPENAI_API_KEY,\n"
        "2,claude-3.5-sonnet,Anthropic,metric_review,2,true,,ANTHROPIC_API_KEY,\n"
        "3,qwen-plus,Qwen,metric_review,3,true,,DASHSCOPE_API_KEY,\n",
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


def test_parse_dirty_live_response_coerced():
    """DeepSeek live 返回脏格式（issues 为字符串、root_match 为中文）应规整为合法结构（回归保护）。"""
    raw = json.dumps(
        [
            {
                "metric_id": "M_SALE_001",
                "naming_score": 4,
                "naming_issues": "metric_en 使用了 mont 而非 month，不符合标准词根组合",
                "caliber_score": 3,
                "caliber_issues": "口径未明确是否含税；未明确统计时区",
                "conflict_risks": ["与 M_SALE_002 可能同义"],
                "root_match": "是",
                "suggestions": "建议补充含税说明",
            }
        ],
        ensure_ascii=False,
    )
    rows = parse_metric_review_response(raw)
    fields = row_to_metric_review_fields(rows[0])
    review = ModelMetricReview.model_validate({"model": "deepseek-v4-flash", **fields})

    assert review.naming_issues == ["metric_en 使用了 mont 而非 month，不符合标准词根组合"]
    assert review.caliber_issues == ["口径未明确是否含税", "未明确统计时区"]
    assert review.conflict_risks == ["与 M_SALE_002 可能同义"]
    assert review.root_match is True
    assert review.naming_score == 4


def test_parse_str_list_literal_coerced():
    """模型返回字符串形式的 JSON 数组（'["a","b"]'）也应正确解析。"""
    fields = row_to_metric_review_fields(
        {
            "metric_id": "M_SALE_002",
            "naming_score": 5,
            "caliber_score": 5,
            "naming_issues": '["a", "b"]',
            "caliber_issues": "[]",
            "conflict_risks": [],
            "root_match": "true",
            "suggestions": "",
        }
    )
    assert fields["naming_issues"] == ["a", "b"]
    assert fields["caliber_issues"] == []
    assert fields["root_match"] is True


def test_parse_missing_optional_fields_ok():
    """缺省 issues 字段时使用空数组，不报错。"""
    fields = row_to_metric_review_fields(
        {
            "metric_id": "M_SALE_003",
            "naming_score": 4,
            "caliber_score": 4,
            "root_match": False,
        }
    )
    assert fields["naming_issues"] == []
    assert fields["caliber_issues"] == []
    assert fields["conflict_risks"] == []
    assert fields["root_match"] is False
