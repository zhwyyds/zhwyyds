"""指标批量生成 — 原子指标 × 修饰词派生（指标批量生成机制.md，IT2-1）。

设计要点：
- 命名规则：`{时间/对比修饰_en}_{原子指标_abbr}`（如 mtd_ord_amt = 本月 + 订单金额）
- 口径自动拼接：`{修饰词中文}：{原子口径}`
- 幂等：metric_en 已存在则跳过；重复执行不产生重复指标
- dry_run 支持：只预览不落盘
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field, fields
from pathlib import Path

from data_governance.io.catalog import MetricRecord, load_catalog
from data_governance.io.metrics_csv import batch_create_metrics, next_metric_id


@dataclass
class ModifierRecord:
    modifier_id: str
    modifier_cn: str
    modifier_en: str
    modifier_abbr: str = ""
    modifier_type: str = ""
    time_scope: str = ""
    description: str = ""
    example_metric: str = ""
    sort_order: str = ""


@dataclass
class GenerateResult:
    generated: list[MetricRecord] = field(default_factory=list)
    existing: list[str] = field(default_factory=list)  # 已存在跳过的 metric_en
    invalid_atomics: list[str] = field(default_factory=list)
    invalid_modifiers: list[str] = field(default_factory=list)
    dry_run: bool = False


def load_modifiers(base_dir: Path) -> list[ModifierRecord]:
    """读取 config/modifier_rules.csv 修饰词库。"""
    path = base_dir / "config" / "modifier_rules.csv"
    if not path.is_file():
        return []
    names = {f.name for f in fields(ModifierRecord)}
    with path.open(newline="", encoding="utf-8") as f:
        return [
            ModifierRecord(**{k: (v or "").strip() for k, v in row.items() if k in names}) for row in csv.DictReader(f)
        ]


def _derive_payload(atomic: MetricRecord, mod: ModifierRecord, metric_id: str) -> dict:
    """单个原子 × 修饰词的派生指标 payload。"""
    en = f"{mod.modifier_en}_{atomic.metric_en}"
    inherit = {
        # 派生指标继承原子的业务属性（修饰词不改变这些维度）
        "category_l1": atomic.category_l1,
        "category_l2": atomic.category_l2,
        "value_type": atomic.value_type,
        "dimensions": atomic.dimensions,
        "scenario": atomic.scenario,
        "reports": atomic.reports,
        "analysis_methods": atomic.analysis_methods,
        "alert_rules": atomic.alert_rules,
        "precision": atomic.precision,
        "data_sources": atomic.data_sources,
        "tree_node_id": atomic.tree_node_id,
        "data_type": atomic.data_type,
    }
    return {
        "metric_id": metric_id,
        "metric_cn": f"{mod.modifier_cn}{atomic.metric_cn}",
        "metric_en": en,
        "domain_code": atomic.domain_code,
        "root_ids": atomic.root_ids,
        "metric_type": "derived",
        "caliber_desc": f"{mod.modifier_cn}：{atomic.caliber_desc or atomic.metric_cn}",
        "unit": atomic.unit,
        "frequency": mod.time_scope or atomic.frequency,
        "owner": atomic.owner,
        "source_model": "batch_generate",
        "review_status": "pending",
        "formula": atomic.formula,
        "tech_caliber": atomic.tech_caliber,
        "source_table": atomic.source_table,
        **inherit,
    }


def generate_derived_metrics(
    base_dir: Path,
    atomic_ids: list[str],
    modifier_ids: list[str],
    *,
    dry_run: bool = False,
) -> GenerateResult:
    """按 原子指标 × 修饰词 批量派生指标并入库（dry_run 只预览）。"""
    catalog = load_catalog(base_dir)
    atomics = {m.metric_id: m for m in catalog.metrics if m.metric_type == "atomic"}
    modifiers = {m.modifier_id: m for m in load_modifiers(base_dir)}
    result = GenerateResult(dry_run=dry_run)

    used_ids = {m.metric_id for m in catalog.metrics}
    seen_en = {m.metric_en for m in catalog.metrics}
    payloads: list[dict] = []

    for aid in atomic_ids:
        atomic = atomics.get(aid)
        if atomic is None:
            result.invalid_atomics.append(aid)
            continue
        for mid in modifier_ids:
            mod = modifiers.get(mid)
            if mod is None:
                if mid not in result.invalid_modifiers:
                    result.invalid_modifiers.append(mid)
                continue
            en = f"{mod.modifier_en}_{atomic.metric_en}"
            if en in seen_en:
                result.existing.append(en)
                continue
            seen_en.add(en)
            new_id = next_metric_id(sorted(used_ids), atomic.domain_code)
            used_ids.add(new_id)
            payloads.append(_derive_payload(atomic, mod, new_id))

    if dry_run:
        result.generated = [MetricRecord.from_row(p) for p in payloads]
    else:
        created, _ = batch_create_metrics(base_dir, payloads)
        result.generated = created
    return result
