from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class RootType(str, Enum):
    noun = "noun"
    verb = "verb"
    adj = "adj"
    unit = "unit"
    time = "time"


class ReviewStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class SourceModel(str, Enum):
    model_consensus = "model_consensus"
    model_majority = "model_majority"
    manual = "manual"


class DecisionType(str, Enum):
    model_consensus = "model_consensus"
    model_majority = "model_majority"
    model_conflict = "model_conflict"


class TermInput(BaseModel):
    cn_term: str
    context: str = ""


class RootGenerationRequest(BaseModel):
    input_type: Literal["root_generation"] = "root_generation"
    domain: str
    terms: list[TermInput] = Field(min_length=1)


class ModelRootResult(BaseModel):
    model: str
    root_en: str
    root_abbr: str
    root_type: RootType
    description: str = ""


class RootComparison(BaseModel):
    root_en_consistent: bool
    root_abbr_consistent: bool
    root_type_consistent: bool
    conflict_fields: list[str] = Field(default_factory=list)


class RootFinalDecision(BaseModel):
    root_en: str
    root_abbr: str
    root_type: RootType
    description: str
    decision_reason: str = ""
    decision_type: DecisionType
    review_status: ReviewStatus


class RootReviewItem(BaseModel):
    cn_term: str
    context: str = ""
    model_results: list[ModelRootResult]
    comparison: RootComparison
    final_decision: RootFinalDecision
    auto_approved: bool


class RootReviewDocument(BaseModel):
    review_id: str
    domain: str
    review_type: Literal["root_generation"] = "root_generation"
    created_at: str
    models_used: list[str]
    items: list[RootReviewItem]


class RootCsvRow(BaseModel):
    root_id: str
    root_cn: str
    root_en: str
    root_abbr: str
    domain_code: str
    root_type: RootType
    description: str
    source_model: SourceModel
    review_status: ReviewStatus
    created_at: str
    updated_at: str
