"""域级治理看板 — 每域红绿灯（IT3-2）。

指标：词根数 / 指标数 / 评分均值 / 等级分布 / 血缘覆盖 / 口径待核查 / 最新发布版本
"""

from __future__ import annotations

from pathlib import Path

from data_governance.io.catalog import load_catalog
from data_governance.io.lineage_loader import list_lineage_domains
from data_governance.release.registry import ReleaseRegistry
from data_governance.scoring.store import load_summary

GRADES = ("S", "A", "B", "C", "D")


def domain_dashboard(base_dir: Path) -> list[dict]:
    """返回每个主题域的治理红绿灯数据。"""
    catalog = load_catalog(base_dir)
    summary = load_summary(base_dir)
    score_by_metric = {r["metric_id"]: r for r in summary}
    lineage_domains = set(list_lineage_domains(base_dir))

    rows: list[dict] = []
    for domain in catalog.domains:
        domain_metrics = [m for m in catalog.metrics if m.domain_code == domain]
        domain_roots = [r for r in catalog.roots if r.domain_code == domain]
        scores = [score_by_metric[m.metric_id] for m in domain_metrics if m.metric_id in score_by_metric]

        grade_dist = {g: 0 for g in GRADES}
        score_sum = 0.0
        for s in scores:
            g = s.get("quality_grade", "D")
            if g in grade_dist:
                grade_dist[g] += 1
            score_sum += float(s.get("quality_score") or 0)

        releases = ReleaseRegistry(base_dir).list_releases(domain)
        latest = max(releases, key=lambda r: r.version) if releases else None

        rows.append(
            {
                "domain": domain,
                "roots_count": len(domain_roots),
                "metrics_count": len(domain_metrics),
                "scored_count": len(scores),
                "score_avg": round(score_sum / len(scores), 1) if scores else None,
                "grade_dist": grade_dist,
                "lineage_ok": domain in lineage_domains,
                "caliber_pending": sum(
                    1 for m in domain_metrics if m.caliber_status in ("pending", "rejected")
                ),
                "latest_version": latest.version_label if latest else None,
                "latest_released_at": latest.released_at if latest else None,
            }
        )
    return rows
