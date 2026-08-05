from data_governance.compare.metrics import build_metric_comparison, decide_metric
from data_governance.schemas.metrics import (
    MetricDecisionType,
    ModelMetricReview,
)


def _review(model: str, naming: int, caliber: int, **kwargs) -> ModelMetricReview:
    defaults = {
        "naming_issues": [],
        "caliber_issues": [],
        "conflict_risks": [],
        "root_match": True,
        "suggestions": "",
    }
    defaults.update(kwargs)
    return ModelMetricReview(
        model=model,
        naming_score=naming,
        caliber_score=caliber,
        **defaults,
    )


def test_monthly_sales_needs_revision():
    reviews = [
        _review("gpt-4o", 5, 4, caliber_issues=["口径未明确是否含税"], suggestions="建议口径中补充是否含税说明"),
        _review(
            "claude-3.5-sonnet",
            5,
            4,
            caliber_issues=["口径未明确是否含税"],
            suggestions="建议补充含税/不含税说明",
        ),
        _review(
            "glm-4",
            4,
            3,
            naming_issues=["建议使用 monthly_sales_amount 更完整"],
            caliber_issues=["口径未明确含税、未明确统计时区"],
            suggestions="建议口径补充含税说明和统计时区",
        ),
    ]
    comp = build_metric_comparison(reviews)
    assert comp.conflict_detected is False
    assert "口径未明确是否含税" in comp.consistent_issues
    assert comp.caliber_score_avg == 3.67

    final = decide_metric(reviews)
    assert final.approved is False
    assert final.decision_type == MetricDecisionType.needs_revision
    assert final.review_status == "pending"
    assert any("含税" in a for a in final.action_items)


def test_conflict_forces_pending():
    reviews = [
        _review("a", 5, 5, conflict_risks=["与 M_SALE_002 同名异义风险"]),
        _review("b", 5, 5),
        _review("c", 5, 5),
    ]
    final = decide_metric(reviews)
    assert final.decision_type == MetricDecisionType.conflict_review
    assert final.review_status == "pending"


def test_all_high_scores_approved():
    reviews = [_review("a", 5, 5), _review("b", 4, 4), _review("c", 5, 4)]
    final = decide_metric(reviews)
    assert final.approved is True
    assert final.decision_type == MetricDecisionType.approved
