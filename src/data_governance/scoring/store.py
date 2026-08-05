"""评分持久化 — scores/{metric_id}.json + scores/_summary.csv。"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from data_governance.io.catalog import ProjectCatalog, load_catalog
from data_governance.scoring.engine import score_metric
from data_governance.scoring.models import ScoreResult, ScoreSummaryRow

SCORES_DIR = "scores"


def _scores_path(base_dir: Path, metric_id: str) -> Path:
    return base_dir / SCORES_DIR / f"{metric_id}.json"


def score_and_persist(
    base_dir: Path,
    metric_id: str,
    *,
    trigger: str = "manual",
    rules_path: Path | None = None,
) -> ScoreResult:
    """对单个指标评分并落盘（含历史追加）。"""
    from data_governance.api.metric_services import load_metric_review_for_metric

    catalog = load_catalog(base_dir)
    metric = next((m for m in catalog.metrics if m.metric_id == metric_id), None)
    if metric is None:
        raise KeyError(metric_id)

    review_detail = load_metric_review_for_metric(base_dir, metric_id)
    result = score_metric(metric, catalog, base_dir, model_review_detail=review_detail)

    # 历史追加
    prev = load_score(base_dir, metric_id)
    history: list[dict] = prev.score_history if prev else []
    history.append(
        {
            "scored_at": result.scored_at,
            "score": result.quality_score,
            "grade": result.grade,
            "trigger": trigger,
        }
    )
    result.score_history = history

    write_score(result, base_dir)
    write_summary(catalog, base_dir)
    return result


def write_score(result: ScoreResult, base_dir: Path) -> Path:
    path = _scores_path(base_dir, result.metric_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_score(base_dir: Path, metric_id: str) -> ScoreResult | None:
    path = _scores_path(base_dir, metric_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return _result_from_dict(data)


def _result_from_dict(data: dict) -> ScoreResult:
    from data_governance.scoring.models import ScoreDimension, ScoreIssue, ScoreItem

    dims = [
        ScoreDimension(
            dim_code=d["dim_code"],
            dim_name=d["dim_name"],
            score=float(d["score"]),
            max_score=float(d["max_score"]),
            status=d.get("status", "pass"),
            items=[ScoreItem(**i) for i in d.get("items", [])],
            detail=d.get("detail", ""),
        )
        for d in data.get("dimensions", [])
    ]
    issues = [ScoreIssue(**i) for i in data.get("issues", [])]
    return ScoreResult(
        metric_id=data["metric_id"],
        metric_cn=data.get("metric_cn", ""),
        metric_en=data.get("metric_en", ""),
        total_score=float(data["total_score"]),
        grade=data.get("grade", "D"),
        scored_at=data.get("scored_at", ""),
        scored_by=data.get("scored_by", ""),
        dimensions=dims,
        special_rules=data.get("special_rules", []),
        issues=issues,
        model_reviews=data.get("model_reviews", []),
        score_history=data.get("score_history", []),
    )


def dim_score(result: ScoreResult, dim_code: str) -> float:
    for d in result.dimensions:
        if d.dim_code == dim_code:
            return d.score
    return 0.0


def write_summary(catalog: ProjectCatalog, base_dir: Path) -> Path:
    """刷新 scores/_summary.csv（遍历所有已评分指标）。"""
    out = base_dir / SCORES_DIR / "_summary.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows: list[ScoreSummaryRow] = []
    for m in catalog.metrics:
        res = load_score(base_dir, m.metric_id)
        if res is None:
            continue
        rows.append(
            ScoreSummaryRow(
                metric_id=m.metric_id,
                metric_cn=m.metric_cn,
                quality_score=res.quality_score,
                quality_grade=res.grade,
                naming=dim_score(res, "naming"),
                root_link=dim_score(res, "root_link"),
                caliber=dim_score(res, "caliber"),
                same_name=dim_score(res, "same_name"),
                lineage=dim_score(res, "lineage"),
                model_review=dim_score(res, "model_review"),
                issues_count=len(res.issues),
                last_scored_at=res.scored_at,
            )
        )
    if not rows:
        out.write_text("", encoding="utf-8")
        return out
    fieldnames = list(rows[0].csv_row().keys())
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r.csv_row())
    return out


def load_summary(base_dir: Path) -> list[dict]:
    out = base_dir / SCORES_DIR / "_summary.csv"
    if not out.is_file():
        return []
    with out.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))
