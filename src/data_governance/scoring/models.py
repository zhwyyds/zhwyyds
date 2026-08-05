"""指标级评分结果模型 — 结构化评分明细，便于 API/UI 展示与持久化。

对应设计文档：指标级质量评分体系.md
六维度：命名规范 / 词根关联 / 口径完整 / 同名同义 / 血缘可查 / 模型评审
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


@dataclass
class ScoreItem:
    """单个评分检查项。"""

    item: str
    score: float
    max_score: float
    status: str  # pass | warn | fail
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScoreDimension:
    """单个评分维度，含若干检查项。"""

    dim_code: str
    dim_name: str
    score: float
    max_score: float
    status: str  # pass | warn | fail
    items: list[ScoreItem] = field(default_factory=list)
    detail: str = ""  # 维度级补充说明（如多模型评审明细）

    def to_dict(self) -> dict:
        d = asdict(self)
        d["items"] = [i.to_dict() for i in self.items]
        return d


@dataclass
class ScoreIssue:
    """待整改项。"""

    priority: str  # P1 | P2 | P3
    dimension: str
    issue: str
    suggestion: str
    fix_action: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScoreResult:
    """单个指标的完整评分结果。"""

    metric_id: str
    metric_cn: str
    metric_en: str
    total_score: float
    grade: str
    scored_at: str
    scored_by: str
    dimensions: list[ScoreDimension]
    special_rules: list[str] = field(default_factory=list)
    issues: list[ScoreIssue] = field(default_factory=list)
    model_reviews: list[dict] = field(default_factory=list)
    score_history: list[dict] = field(default_factory=list)

    @property
    def quality_score(self) -> int:
        return round(self.total_score)

    @property
    def quality_grade(self) -> str:
        return self.grade

    def to_dict(self) -> dict:
        return {
            "metric_id": self.metric_id,
            "metric_cn": self.metric_cn,
            "metric_en": self.metric_en,
            "total_score": self.total_score,
            "grade": self.grade,
            "scored_at": self.scored_at,
            "scored_by": self.scored_by,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "special_rules": self.special_rules,
            "issues": [i.to_dict() for i in self.issues],
            "model_reviews": self.model_reviews,
            "score_history": self.score_history,
        }


@dataclass
class ScoreSummaryRow:
    """评分汇总单行（写入 scores/_summary.csv）。"""

    metric_id: str
    metric_cn: str
    quality_score: int
    quality_grade: str
    naming: float
    root_link: float
    caliber: float
    same_name: float
    lineage: float
    model_review: float
    issues_count: int
    last_scored_at: str

    def csv_row(self) -> dict[str, str]:
        return {
            "metric_id": self.metric_id,
            "metric_cn": self.metric_cn,
            "quality_score": str(self.quality_score),
            "quality_grade": self.quality_grade,
            "naming": str(self.naming),
            "root_link": str(self.root_link),
            "caliber": str(self.caliber),
            "same_name": str(self.same_name),
            "lineage": str(self.lineage),
            "model_review": str(self.model_review),
            "issues_count": str(self.issues_count),
            "last_scored_at": self.last_scored_at,
        }


def dim_score_by_code(result: ScoreResult, dim_code: str) -> float:
    for d in result.dimensions:
        if d.dim_code == dim_code:
            return d.score
    return 0.0
