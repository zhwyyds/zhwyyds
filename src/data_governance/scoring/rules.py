"""评分规则加载器 — 读取 config/scoring_rules.json。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from data_governance.paths import repo_root

DEFAULT_RULES_PATH = "config/scoring_rules.json"


@dataclass
class ItemRule:
    item: str
    max: float
    rule: str = ""
    veto: bool = False
    partial_ratio: float = 0.0
    deduct_per_case: float = 0.0


@dataclass
class DimensionRule:
    dim_code: str
    dim_name: str
    max_score: float
    items: list[ItemRule] = field(default_factory=list)


@dataclass
class SpecialRule:
    rule: str
    effect: str  # max_grade_C | max_grade_B
    description: str = ""


@dataclass
class ScoringRuleSet:
    version: str
    total_max_score: float
    scored_by: str
    grade_thresholds: dict[str, int]
    dimensions: list[DimensionRule]
    special_rules: list[SpecialRule]

    def grade_for(self, total: float) -> str:
        for g in ("S", "A", "B", "C", "D"):
            if total >= self.grade_thresholds.get(g, 0):
                return g
        return "D"


def load_scoring_rules(config_path: Path | None = None) -> ScoringRuleSet:
    """加载评分规则；缺省读取 <base>/config/scoring_rules.json。"""
    path = config_path or (repo_root() / DEFAULT_RULES_PATH)
    if not path.is_file():
        raise FileNotFoundError(f"scoring rules not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))

    dims: list[DimensionRule] = []
    for d in data.get("dimensions", []):
        items = [
            ItemRule(
                item=it["item"],
                max=float(it["max"]),
                rule=it.get("rule", ""),
                veto=bool(it.get("veto", False)),
                partial_ratio=float(it.get("partial_ratio", 0.0)),
                deduct_per_case=float(it.get("deduct_per_case", 0.0)),
            )
            for it in d.get("items", [])
        ]
        dims.append(
            DimensionRule(
                dim_code=d["dim_code"],
                dim_name=d["dim_name"],
                max_score=float(d["max_score"]),
                items=items,
            )
        )

    specials = [
        SpecialRule(rule=s["rule"], effect=s["effect"], description=s.get("description", ""))
        for s in data.get("special_rules", [])
    ]

    return ScoringRuleSet(
        version=data.get("version", "1.0"),
        total_max_score=float(data.get("total_max_score", 100)),
        scored_by=data.get("scored_by", "metric_scorer_v1"),
        grade_thresholds={k: int(v) for k, v in data.get("grade_thresholds", {}).items()},
        dimensions=dims,
        special_rules=specials,
    )
