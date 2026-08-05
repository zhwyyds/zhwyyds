from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from data_governance.config_loader import load_domains


@dataclass
class RootRecord:
    domain_code: str
    root_id: str
    root_cn: str
    root_en: str
    root_abbr: str
    root_type: str
    description: str = ""
    source_model: str = ""
    review_status: str = ""
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row: dict[str, str]) -> RootRecord:
        """从 CSV dict 行构建 RootRecord，自动处理缺失字段。"""
        return cls(**{f.name: (row.get(f.name) or "").strip() for f in fields(cls)})


@dataclass
class MetricRecord:
    domain_code: str
    metric_id: str
    metric_cn: str
    metric_en: str
    metric_abbr: str
    root_ids: str
    metric_type: str = ""
    caliber_desc: str = ""
    unit: str = ""
    frequency: str = ""
    owner: str = ""
    source_model: str = ""
    review_status: str = ""
    category_l1: str = ""
    category_l2: str = ""
    value_type: str = ""
    dimensions: str = ""
    scenario: str = ""
    reports: str = ""
    formula: str = ""
    analysis_methods: str = ""
    alert_rules: str = ""
    precision: str = ""
    data_sources: str = ""
    tech_caliber: str = ""
    tree_node_id: str = ""
    data_type: str = ""
    formula_cn: str = ""
    source_table: str = ""
    version: str = ""
    version_history: str = ""
    offline_reason: str = ""
    offline_note: str = ""
    objection_status: str = ""
    objection_note: str = ""
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row: dict[str, str]) -> MetricRecord:
        """从 CSV dict 行构建 MetricRecord，自动处理缺失字段。"""
        return cls(**{f.name: (row.get(f.name) or "").strip() for f in fields(cls)})

    def to_row(self) -> dict[str, str]:
        """转换为 CSV dict 行，所有值转为 str。"""
        return {k: str(v or "") for k, v in asdict(self).items()}


@dataclass
class ProjectCatalog:
    domains: list[str]
    roots: list[RootRecord] = field(default_factory=list)
    metrics: list[MetricRecord] = field(default_factory=list)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    """读取 CSV 文件，返回 dict 列表，空值统一为空字符串。"""
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


def load_catalog(base_dir: Path) -> ProjectCatalog:
    """加载项目全量目录：域、词根、指标。"""
    domains = [d.domain_code for d in load_domains(base_dir / "config" / "domains.csv")]

    roots: list[RootRecord] = []
    roots_dir = base_dir / "roots"
    for domain in domains:
        for row in _read_csv_rows(roots_dir / f"{domain}_roots.csv"):
            row.setdefault("domain_code", domain)
            roots.append(RootRecord.from_row(row))

    metrics: list[MetricRecord] = []
    metrics_dir = base_dir / "metrics"
    for domain in domains:
        for row in _read_csv_rows(metrics_dir / f"{domain}_metrics.csv"):
            row.setdefault("domain_code", domain)
            metrics.append(MetricRecord.from_row(row))

    return ProjectCatalog(domains=domains, roots=roots, metrics=metrics)
