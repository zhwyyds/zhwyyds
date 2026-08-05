"""数据自检 — 扫描 roots/metrics/lineage/config 完整性（IT1-2）。

检查项：
- CSV 必须可按 UTF-8 读取、字段数与表头一致
- 必填字段非空（词根: root_id/root_cn/root_en；指标: metric_id/metric_cn/metric_en/domain_code）
- 无重复 ID
- 引用完整性：指标 root_ids 必须指向已注册词根；domain_code 必须在域配置中
- 血缘 JSON 可解析，lineages 条目含 lineage_id / target_table
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

ROOT_REQUIRED = ("root_id", "root_cn", "root_en")
METRIC_REQUIRED = ("metric_id", "metric_cn", "metric_en", "domain_code")


@dataclass
class ValidationIssue:
    severity: str  # error | warning
    file: str
    message: str


def _check_csv(
    path: Path,
    required: tuple[str, ...],
    issues: list[ValidationIssue],
) -> list[dict[str, str]]:
    """校验单个 CSV 的编码/字段数/必填/重复 ID，返回行记录供引用检查。"""
    rows: list[dict[str, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        issues.append(ValidationIssue("error", path.name, f"无法按 UTF-8 读取: {exc}"))
        return rows

    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        issues.append(ValidationIssue("warning", path.name, "空文件（无内容）"))
        return rows

    header = next(csv.reader([lines[0]]))
    header = [h.strip() for h in header]
    seen: set[str] = set()
    for lineno, raw in enumerate(lines[1:], start=2):
        row = next(csv.reader([raw]))
        if len(row) != len(header):
            issues.append(
                ValidationIssue("error", path.name, f"第 {lineno} 行字段数 {len(row)} != 表头 {len(header)}")
            )
            continue
        rec = {k.strip(): (v or "").strip() for k, v in zip(header, row, strict=True)}
        for field in required:
            if not rec.get(field):
                issues.append(ValidationIssue("error", path.name, f"第 {lineno} 行缺少必填字段 {field}"))
        rid = rec.get("root_id") or rec.get("metric_id") or ""
        if rid:
            if rid in seen:
                issues.append(ValidationIssue("error", path.name, f"重复 ID: {rid}"))
            seen.add(rid)
        rows.append(rec)
    return rows


def _load_domain_codes(base_dir: Path) -> list[str]:
    path = base_dir / "config" / "domains.csv"
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [r["domain_code"] for r in csv.DictReader(f) if r.get("domain_code")]


def validate_lineage_data(data: object) -> list[ValidationIssue]:
    """校验血缘 JSON 数据（顶层对象 + lineages 条目结构），供上传与自检共用。"""
    issues: list[ValidationIssue] = []
    if not isinstance(data, dict):
        issues.append(ValidationIssue("error", "(lineage)", "JSON 顶层应为对象"))
        return issues
    lineages = data.get("lineages")
    if not isinstance(lineages, list):
        issues.append(ValidationIssue("warning", "(lineage)", "缺少 lineages 数组"))
        return issues
    for item in lineages:
        if not isinstance(item, dict):
            issues.append(ValidationIssue("error", "(lineage)", "lineages 条目应为对象"))
            continue
        if not (item.get("lineage_id") or "").strip():
            issues.append(ValidationIssue("error", "(lineage)", "lineages 条目缺少 lineage_id"))
        if not (item.get("target_table") or "").strip():
            issues.append(
                ValidationIssue("warning", "(lineage)", f"lineage {item.get('lineage_id')} 缺少 target_table")
            )
    return issues


def _check_lineage(path: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        issues.append(ValidationIssue("error", path.name, f"JSON 无法解析: {exc}"))
        return issues
    for issue in validate_lineage_data(data):
        issue.file = path.name
        issues.append(issue)
    return issues


def validate_project(base_dir: Path) -> list[ValidationIssue]:
    """扫描项目数据目录，返回问题清单（error 需修复，warning 提示性）。"""
    issues: list[ValidationIssue] = []
    domains = _load_domain_codes(base_dir)
    if not domains:
        issues.append(ValidationIssue("error", "config/domains.csv", "无任何主题域配置"))
        return issues

    domain_set = set(domains)
    roots_dir, metrics_dir = base_dir / "roots", base_dir / "metrics"
    all_root_ids: set[str] = set()

    # 阶段一：词根
    for domain in domains:
        path = roots_dir / f"{domain}_roots.csv"
        if not path.is_file():
            issues.append(ValidationIssue("warning", path.name, f"缺少词根文件（域 {domain}）"))
            continue
        rows = _check_csv(path, ROOT_REQUIRED, issues)
        for r in rows:
            if r.get("root_id"):
                all_root_ids.add(r["root_id"])
            dc = r.get("domain_code")
            if dc and dc not in domain_set:
                issues.append(
                    ValidationIssue("error", path.name, f"词根 {r.get('root_id')} 的 domain_code={dc} 不在域配置中")
                )

    # 阶段二：指标（引用完整性）
    for domain in domains:
        path = metrics_dir / f"{domain}_metrics.csv"
        if not path.is_file():
            issues.append(ValidationIssue("warning", path.name, f"缺少指标文件（域 {domain}）"))
            continue
        rows = _check_csv(path, METRIC_REQUIRED, issues)
        for r in rows:
            mid = r.get("metric_id") or ""
            dc = r.get("domain_code")
            if dc and dc not in domain_set:
                issues.append(ValidationIssue("error", path.name, f"指标 {mid} 的 domain_code={dc} 不在域配置中"))
            for rid in [x.strip() for x in (r.get("root_ids") or "").split(";") if x.strip()]:
                if rid not in all_root_ids:
                    issues.append(ValidationIssue("error", path.name, f"指标 {mid} 引用未注册词根 {rid}"))

    # 阶段三：血缘
    lineage_dir = base_dir / "lineage"
    if lineage_dir.is_dir():
        for p in sorted(lineage_dir.glob("*_lineage.json")):
            issues.extend(_check_lineage(p))

    return issues
