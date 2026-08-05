from __future__ import annotations

from collections import Counter

from data_governance.schemas.metrics import (
    MetricComparison,
    MetricDecisionType,
    MetricFinalDecision,
    ModelMetricReview,
)


def _issues_with_majority(reviews: list[ModelMetricReview], field: str, min_models: int = 2) -> list[str]:
    counts: Counter[str] = Counter()
    for r in reviews:
        issues = getattr(r, field)
        for issue in issues:
            text = str(issue).strip()
            if text:
                counts[text] += 1
    return [issue for issue, cnt in counts.items() if cnt >= min_models]


def build_metric_comparison(reviews: list[ModelMetricReview]) -> MetricComparison:
    naming_avg = sum(r.naming_score for r in reviews) / len(reviews)
    caliber_avg = sum(r.caliber_score for r in reviews) / len(reviews)
    consistent = _issues_with_majority(reviews, "caliber_issues")
    consistent += [i for i in _issues_with_majority(reviews, "naming_issues") if i not in consistent]
    conflict_detected = any(r.conflict_risks for r in reviews)
    return MetricComparison(
        naming_score_avg=round(naming_avg, 2),
        caliber_score_avg=round(caliber_avg, 2),
        consistent_issues=consistent,
        conflict_detected=conflict_detected,
    )


def _collect_action_items(reviews: list[ModelMetricReview], comparison: MetricComparison) -> list[str]:
    items: list[str] = list(comparison.consistent_issues)
    for r in reviews:
        if r.suggestions and r.suggestions not in items:
            items.append(r.suggestions)
    return items


def decide_metric(reviews: list[ModelMetricReview]) -> MetricFinalDecision:
    if len(reviews) < 1:
        raise ValueError("need at least 1 model review")

    comparison = build_metric_comparison(reviews)

    if comparison.conflict_detected:
        return MetricFinalDecision(
            approved=False,
            decision_type=MetricDecisionType.conflict_review,
            action_items=_collect_action_items(reviews, comparison),
            review_status="pending",
        )

    all_high = all(r.naming_score >= 4 and r.caliber_score >= 4 for r in reviews)
    if all_high:
        return MetricFinalDecision(
            approved=True,
            decision_type=MetricDecisionType.approved,
            action_items=[],
            review_status="approved",
        )

    return MetricFinalDecision(
        approved=False,
        decision_type=MetricDecisionType.needs_revision,
        action_items=_collect_action_items(reviews, comparison),
        review_status="pending",
    )
