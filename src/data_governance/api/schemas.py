"""API 请求/响应 Pydantic 模型 — 替代 dict=Body() 的无校验写法。"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ── 指标创建/更新 ──────────────────────────────────────────────────────


class MetricCreateRequest(BaseModel):
    """POST /api/v1/metrics 请求体。"""

    metric_id: str = Field(..., min_length=1, description="指标ID，格式 M_DOMAIN_XXX")
    metric_cn: str = Field(..., min_length=1, description="指标中文名")
    metric_en: str = Field("", description="指标英文名 (snake_case)")
    metric_abbr: str = Field("", description="指标缩写")
    domain_code: str = Field("", description="域代码，为空时从 metric_id 推断")
    root_ids: str = Field("", description="词根ID列表，分号分隔")
    metric_type: str = Field("atomic", description="指标类型")
    caliber_desc: str = Field("", description="口径描述")
    unit: str = Field("", description="单位")
    frequency: str = Field("", description="更新频率")
    owner: str = Field("", description="负责人")
    category_l1: str = Field("", description="一级分类")
    category_l2: str = Field("", description="二级分类")
    value_type: str = Field("", description="值类型")
    dimensions: str = Field("", description="维度")
    scenario: str = Field("", description="适用场景")
    formula: str = Field("", description="计算公式")
    formula_cn: str = Field("", description="中文公式")
    source_table: str = Field("", description="来源表")
    precision: str = Field("", description="精度")


class MetricUpdateRequest(BaseModel):
    """PUT /api/v1/metrics/{metric_id} 请求体。所有字段可选。"""

    metric_cn: str | None = None
    metric_en: str | None = None
    metric_abbr: str | None = None
    root_ids: str | None = None
    metric_type: str | None = None
    caliber_desc: str | None = None
    unit: str | None = None
    frequency: str | None = None
    owner: str | None = None
    source_model: str | None = None
    review_status: str | None = None
    category_l1: str | None = None
    category_l2: str | None = None
    value_type: str | None = None
    dimensions: str | None = None
    scenario: str | None = None
    reports: str | None = None
    formula: str | None = None
    formula_cn: str | None = None
    source_table: str | None = None
    tree_node_id: str | None = None
    offline_reason: str | None = None
    offline_note: str | None = None
    objection_status: str | None = None
    objection_note: str | None = None
    data_type: str | None = None
    data_sources: str | None = None
    tech_caliber: str | None = None
    alert_rules: str | None = None
    analysis_methods: str | None = None
    precision: str | None = None


# ── 通用响应 ──────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str
    base_dir: str


class StatsResponse(BaseModel):
    total: int
    pending_review: int
    published: int
    offline: int


class RevisionApplyRequest(BaseModel):
    """POST /api/metrics/{id}/review/{rid}/apply-revision 请求体。

    fields 为空列表表示应用 AI 修订建议的全部字段。
    """

    fields: list[str] = Field(default_factory=list)
    checked_by: str = ""
