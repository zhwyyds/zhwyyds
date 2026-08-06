from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from data_governance.io.catalog import MetricRecord, ProjectCatalog, load_catalog

REVIEWED_SOURCE = frozenset({"model_consensus", "model_majority"})
METRIC_EN_RE = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass
class CheckFinding:
    code: str
    message: str
    severity: str = "info"  # info | warn | error


@dataclass
class SubScore:
    name: str
    max_points: float
    points: float
    detail: str = ""
    automated: bool = True


@dataclass
class DimensionScore:
    name: str
    weight_label: str
    max_points: float
    points: float
    subscores: list[SubScore] = field(default_factory=list)
    passed: bool = True


@dataclass
class AcceptanceReport:
    evaluated_at: str
    catalog: ProjectCatalog
    dimensions: list[DimensionScore]
    total_points: float
    grade: str
    veto: bool
    veto_reason: str = ""
    findings: list[CheckFinding] = field(default_factory=list)
    skipped_notes: list[str] = field(default_factory=list)

    @property
    def metric_total(self) -> int:
        return len(self.catalog.metrics)

    @property
    def root_total(self) -> int:
        return len(self.catalog.roots)


def _rate_ge_threshold(
    rate: float, threshold: float, max_score: float, step: float = 0.05, penalty: float = 2.0
) -> float:
    if rate >= threshold:
        return max_score
    if rate <= 0 and threshold > 0:
        drops = math.ceil(threshold / step)
        return max(0.0, max_score - drops * penalty)
    short = threshold - rate
    drops = math.ceil(short / step)
    return max(0.0, max_score - drops * penalty)


def _safe_rate(num: int, den: int) -> float:
    if den == 0:
        return 0.0
    return num / den


def score_root_coverage(catalog: ProjectCatalog) -> DimensionScore:
    """验收维度：词根覆盖度——指标 root_ids 引用是否齐全、metric_en 能否由词根还原。"""
    subs: list[SubScore] = []
    metrics = catalog.metrics
    roots = catalog.roots

    with_roots = sum(1 for m in metrics if m.root_ids.strip())
    rate = _safe_rate(with_roots, len(metrics))
    subs.append(
        SubScore(
            "词根入库率",
            8,
            _rate_ge_threshold(rate, 0.95, 8),
            f"{with_roots}/{len(metrics)} ({rate:.1%})",
        )
    )

    domain_counts: dict[str, int] = defaultdict(int)
    for r in roots:
        domain_counts[r.domain_code] += 1
    domains_ok = sum(1 for d in catalog.domains if domain_counts.get(d, 0) >= 10)
    if len(catalog.domains) == 0:
        dom_score = 0.0
    elif domains_ok == len(catalog.domains):
        dom_score = 6.0
    else:
        dom_score = max(0.0, 6.0 * domains_ok / len(catalog.domains))
    subs.append(
        SubScore(
            "词根完整性",
            6,
            dom_score,
            f"{domains_ok}/{len(catalog.domains)} 域≥10词根",
        )
    )

    required_fields = ("root_cn", "root_en", "root_abbr", "root_type")
    if roots:
        complete = sum(1 for r in roots if all(getattr(r, f).strip() for f in required_fields))
        field_rate = complete / len(roots)
    else:
        field_rate = 0.0
    subs.append(
        SubScore(
            "词根字段完整",
            3,
            _rate_ge_threshold(field_rate, 0.95, 3),
            f"完整率 {field_rate:.1%}",
        )
    )

    dup_count = 0
    by_domain: dict[str, set[str]] = defaultdict(set)
    for r in roots:
        if r.root_cn in by_domain[r.domain_code]:
            dup_count += 1
        by_domain[r.domain_code].add(r.root_cn)
    dup_score = 3.0 if dup_count == 0 else max(0.0, 3.0 - dup_count)
    subs.append(SubScore("词根无重复", 3, dup_score, f"重复 {dup_count} 处"))

    pts = sum(s.points for s in subs)
    return DimensionScore("词根覆盖", "20%", 20, pts, subs, passed=pts >= 14)


def score_naming(catalog: ProjectCatalog) -> DimensionScore:
    subs: list[SubScore] = []
    metrics = catalog.metrics

    en_ok = sum(1 for m in metrics if m.metric_en.strip() and METRIC_EN_RE.match(m.metric_en))
    en_rate = _safe_rate(en_ok, len(metrics))
    subs.append(SubScore("英文命名率", 8, _rate_ge_threshold(en_rate, 0.95, 8), f"{en_rate:.1%}"))

    subs.append(
        SubScore(
            "拼音清除率",
            5,
            0.0,
            "未提供迁移对照表，未自动评估",
            automated=False,
        )
    )

    fmt_ok = sum(1 for m in metrics if m.metric_en.strip() and METRIC_EN_RE.match(m.metric_en))
    fmt_rate = _safe_rate(fmt_ok, len(metrics))
    fmt_pts = 2.0 if fmt_rate >= 0.99 else (1.0 if fmt_rate >= 0.9 else 0.0)
    subs.append(SubScore("命名格式一致", 2, fmt_pts, f"snake_case 合规 {fmt_rate:.1%}"))

    pts = sum(s.points for s in subs)
    return DimensionScore("命名规范", "20%", 20, pts, subs, passed=pts >= 14)


def score_homonym_synonym(
    catalog: ProjectCatalog,
    root_abbrs: set[str],
) -> tuple[DimensionScore, bool, list[CheckFinding]]:
    findings: list[CheckFinding] = []
    metrics = catalog.metrics

    by_en: dict[str, set[str]] = defaultdict(set)
    for m in metrics:
        if not m.metric_en.strip():
            continue
        by_en[m.metric_en].add(m.caliber_desc.strip())

    homonym_cases = [en for en, descs in by_en.items() if len(descs) > 1]
    veto = len(homonym_cases) > 0
    homonym_pts = 0.0 if veto else 10.0
    if homonym_cases:
        findings.append(
            CheckFinding(
                "homonym_veto",
                f"同名异义 {len(homonym_cases)} 组: {', '.join(homonym_cases[:5])}",
                "error",
            )
        )

    by_caliber: dict[str, set[str]] = defaultdict(set)
    for m in metrics:
        cal = m.caliber_desc.strip()
        if not cal:
            continue
        by_caliber[cal].add(m.metric_en.strip())

    synonym_groups = [cal for cal, ens in by_caliber.items() if len(ens) > 1]
    synonym_cases = len(synonym_groups)
    synonym_pts = max(0.0, 10.0 - synonym_cases * 3.0)

    def en_matches_roots(m: MetricRecord) -> bool:
        if not m.metric_en.strip():
            return False
        tokens = [t for t in m.metric_en.split("_") if t]
        return bool(tokens) and all(t in root_abbrs for t in tokens)

    match_ok = sum(1 for m in metrics if en_matches_roots(m))
    match_rate = _safe_rate(match_ok, len(metrics))
    match_pts = _rate_ge_threshold(match_rate, 0.90, 5.0)

    subs = [
        SubScore("同名异义检查", 10, homonym_pts, f"{len(homonym_cases)} 组"),
        SubScore(
            "同义异名检查",
            10,
            synonym_pts,
            f"{synonym_cases} 组（精确 caliber_desc，非语义聚类）",
        ),
        SubScore("名称-词根一致性", 5, match_pts, f"{match_rate:.1%}"),
    ]
    pts = sum(s.points for s in subs)
    passed = not veto and pts >= 18
    return DimensionScore("同名同义", "25%", 25, pts, subs, passed=passed), veto, findings


def score_caliber(catalog: ProjectCatalog) -> DimensionScore:
    metrics = catalog.metrics
    filled = sum(1 for m in metrics if m.caliber_desc.strip())
    rate = _safe_rate(filled, len(metrics))
    subs = [
        SubScore("口径定义覆盖率", 8, _rate_ge_threshold(rate, 0.95, 8), f"{rate:.1%}"),
        SubScore("口径描述质量", 4, 0.0, "需大模型评审，M5 未实现", automated=False),
        SubScore("口径无矛盾", 3, 0.0, "需大模型交叉评审，M5 未实现", automated=False),
    ]
    pts = sum(s.points for s in subs)
    return DimensionScore("口径完整", "15%", 15, pts, subs, passed=pts >= 10)


def _load_lineage_entries(base_dir: Path, domains: list[str]) -> list[dict]:
    entries: list[dict] = []
    for d in domains:
        path = base_dir / "lineage" / f"{d}_lineage.json"
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for item in data.get("lineages") or []:
            if isinstance(item, dict):
                entries.append(item)
    return entries


def score_lineage(base_dir: Path, catalog: ProjectCatalog) -> DimensionScore:
    domains = catalog.domains
    present = sum(1 for d in domains if (base_dir / "lineage" / f"{d}_lineage.json").is_file())
    missing = len(domains) - present
    file_pts = max(0.0, 4.0 - missing * 0.3)

    entries = _load_lineage_entries(base_dir, domains)
    core = [e for e in entries if str(e.get("target_layer", "")).lower() in ("dwd", "dws")]
    core_rate = _safe_rate(len(core), len(entries)) if entries else 0.0
    core_pts = _rate_ge_threshold(core_rate, 0.80, 3.0)

    with_cols = sum(1 for e in entries if e.get("column_mappings"))
    col_rate = _safe_rate(with_cols, len(entries)) if entries else 0.0
    col_pts = _rate_ge_threshold(col_rate, 0.60, 2.0)

    with_metrics = sum(1 for e in entries if e.get("related_metrics"))
    met_rate = _safe_rate(with_metrics, len(entries)) if entries else 0.0
    met_pts = _rate_ge_threshold(met_rate, 0.50, 1.0)

    subs = [
        SubScore("血缘文件覆盖", 4, file_pts, f"{present}/{len(domains)} 域有文件"),
        SubScore("核心表覆盖", 3, core_pts, f"dwd/dws 占比 {core_rate:.1%}"),
        SubScore("字段映射完整", 2, col_pts, f"column_mappings {col_rate:.1%}"),
        SubScore("血缘可追溯", 1, met_pts, f"related_metrics {met_rate:.1%}"),
    ]
    pts = sum(s.points for s in subs)
    return DimensionScore("血缘可查", "10%", 10, pts, subs, passed=pts >= 7)


def _review_json_complete(path: Path, review_type: str) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    items = data.get("items") or []
    if not items:
        return False
    for item in items:
        if review_type == "root":
            if not item.get("model_results") or not item.get("comparison") or not item.get("final_decision"):
                return False
        else:
            if not item.get("model_reviews") or not item.get("comparison") or not item.get("final_decision"):
                return False
    return True


def score_model_review(base_dir: Path, catalog: ProjectCatalog) -> DimensionScore:
    roots = catalog.roots
    metrics = catalog.metrics

    root_reviewed = sum(1 for r in roots if r.source_model in REVIEWED_SOURCE)
    root_rate = _safe_rate(root_reviewed, len(roots))
    root_pts = _rate_ge_threshold(root_rate, 0.80, 4.0)

    metric_reviewed = sum(1 for m in metrics if m.source_model in REVIEWED_SOURCE)
    metric_rate = _safe_rate(metric_reviewed, len(metrics))
    metric_pts = _rate_ge_threshold(metric_rate, 0.80, 4.0)

    root_files = list((base_dir / "reviews" / "root_reviews").glob("*_root_review_*.json"))
    metric_files = list((base_dir / "reviews" / "metric_reviews").glob("*_metric_review_*.json"))
    complete = sum(1 for p in root_files if _review_json_complete(p, "root"))
    complete += sum(1 for p in metric_files if _review_json_complete(p, "metric"))
    total_files = len(root_files) + len(metric_files)
    if total_files == 0:
        rec_pts = 0.0
        rec_detail = "无评审 JSON"
    else:
        rec_pts = 2.0 * complete / total_files
        rec_detail = f"完整 {complete}/{total_files} 份"

    subs = [
        SubScore("词根评审执行率", 4, root_pts, f"{root_rate:.1%}"),
        SubScore("指标评审执行率", 4, metric_pts, f"{metric_rate:.1%}"),
        SubScore("评审记录完整性", 2, rec_pts, rec_detail),
    ]
    pts = sum(s.points for s in subs)
    return DimensionScore("模型评审", "10%", 10, pts, subs, passed=pts >= 7)


def grade_from_total(total: float, veto: bool) -> str:
    if veto:
        return "C"
    if total >= 95:
        return "S"
    if total >= 85:
        return "A"
    if total >= 70:
        return "B"
    return "C"


def run_acceptance(base_dir: Path) -> AcceptanceReport:
    catalog = load_catalog(base_dir)
    root_abbrs = {r.root_abbr for r in catalog.roots if r.root_abbr.strip()}

    dimensions = [
        score_root_coverage(catalog),
        score_naming(catalog),
    ]
    homonym_dim, veto, findings = score_homonym_synonym(catalog, root_abbrs)
    dimensions.append(homonym_dim)
    dimensions.extend(
        [
            score_caliber(catalog),
            score_lineage(base_dir, catalog),
            score_model_review(base_dir, catalog),
        ]
    )

    total = round(sum(d.points for d in dimensions), 2)
    grade = grade_from_total(total, veto)
    skipped = [
        "拼音清除率：需迁移前后对照表",
        "同义异名（部分）：当前为 caliber_desc 精确匹配，语义聚类需大模型",
        "口径描述质量 / 口径无矛盾：需大模型",
    ]

    return AcceptanceReport(
        evaluated_at=date.today().isoformat(),
        catalog=catalog,
        dimensions=dimensions,
        total_points=total,
        grade=grade,
        veto=veto,
        veto_reason="存在同名异义" if veto else "",
        findings=findings,
        skipped_notes=skipped,
    )
