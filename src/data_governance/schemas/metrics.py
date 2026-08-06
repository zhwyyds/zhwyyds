from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class MetricDecisionType(str, Enum):
    approved = "approved"
    needs_revision = "needs_revision"
    conflict_review = "conflict_review"


class MetricInput(BaseModel):
    metric_id: str
    metric_cn: str
    metric_en: str
    caliber_desc: str
    root_ids: list[str] = Field(default_factory=list)
    unit: str = ""
    frequency: str = ""


class MetricReviewRequest(BaseModel):
    input_type: Literal["metric_review"] = "metric_review"
    domain: str
    metrics: list[MetricInput] = Field(min_length=1)


class MetricRevision(BaseModel):
    """评审后 AI 产出的结构化修订建议（人工勾选后纳入指标定义）。"""

    metric_cn: str | None = None
    metric_en: str | None = None
    caliber_desc: str | None = None
    unit: str | None = None
    frequency: str | None = None
    root_ids: list[str] | None = None
    summary: str = ""

    def as_dict(self) -> dict:
        out: dict = {}
        for f in ("metric_cn", "metric_en", "caliber_desc", "unit", "frequency", "root_ids"):
            v = getattr(self, f)
            if v is not None and v != "" and v != []:
                out[f] = v
        if self.summary:
            out["summary"] = self.summary
        return out


class ModelMetricReview(BaseModel):
    model: str
    naming_score: int = Field(ge=1, le=5)
    naming_issues: list[str] = Field(default_factory=list)
    caliber_score: int = Field(ge=1, le=5)
    caliber_issues: list[str] = Field(default_factory=list)
    conflict_risks: list[str] = Field(default_factory=list)
    root_match: bool
    suggestions: str = ""
    revision: MetricRevision | None = None

    @field_validator("naming_issues", "caliber_issues", "conflict_risks", mode="before")
    @classmethod
    def _coerce_list(cls, v):
        if v is None:
            return []
        return v


class MetricComparison(BaseModel):
    naming_score_avg: float
    caliber_score_avg: float
    consistent_issues: list[str] = Field(default_factory=list)
    conflict_detected: bool = False


class MetricFinalDecision(BaseModel):
    approved: bool
    decision_type: MetricDecisionType
    action_items: list[str] = Field(default_factory=list)
    review_status: Literal["pending", "approved"]


class MetricReviewItem(BaseModel):
    metric_id: str
    metric_en: str
    model_reviews: list[ModelMetricReview]
    comparison: MetricComparison
    final_decision: MetricFinalDecision


class MetricReviewDocument(BaseModel):
    review_id: str
    domain: str
    review_type: Literal["metric_review"] = "metric_review"
    created_at: str
    models_used: list[str]
    review_source: Literal["mock", "live"] = "live"
    items: list[MetricReviewItem]
