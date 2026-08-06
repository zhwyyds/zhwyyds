"""评分引擎与持久化测试（IT1-1）。"""

from pathlib import Path

from data_governance.io.catalog import MetricRecord, load_catalog
from data_governance.scoring.engine import score_metric
from data_governance.scoring.pinyin import is_pinyin_token
from data_governance.scoring.rules import load_scoring_rules
from data_governance.scoring.store import (
    dim_score,
    load_score,
    load_summary,
    score_and_persist,
)

EXPECTED_DIMS = {"naming", "root_link", "caliber", "same_name", "lineage", "model_review"}


def _metric(**kw) -> MetricRecord:
    base = dict(
        domain_code="sale",
        metric_id="M_TEST",
        metric_cn="测试指标",
        metric_en="test_metric",
        root_ids="",
        metric_type="atomic",
        caliber_desc="统计周期为自然月，计算公式为 SUM(x)，粒度为订单行级",
        review_status="approved",
    )
    base.update(kw)
    return MetricRecord(**base)


def test_score_metric_six_dimensions(mini_project: Path):
    catalog = load_catalog(mini_project)
    metric = next(m for m in catalog.metrics if m.metric_id == "M_SALE_001")
    result = score_metric(metric, catalog, mini_project)
    assert {d.dim_code for d in result.dimensions} == EXPECTED_DIMS
    assert result.total_score >= 0
    assert result.grade in {"S", "A", "B", "C", "D"}
    assert isinstance(result.issues, list)


def test_pinyin_metric_flagged_and_capped(mini_project: Path):
    """metric_en 残留拼音 → 特殊规则「拼音残留」→ 等级封顶 B。"""
    catalog = load_catalog(mini_project)
    metric = _metric(metric_id="M_SALE_999", metric_en="xiaoshou_jine")
    result = score_metric(metric, catalog, mini_project)
    assert "拼音残留" in result.special_rules
    assert result.grade in {"B", "C", "D"}


def test_empty_caliber_capped_at_c(mini_project: Path):
    """口径为空 → 特殊规则「口径为空」→ 等级封顶 C。"""
    catalog = load_catalog(mini_project)
    metric = _metric(metric_id="M_SALE_998", caliber_desc="")
    result = score_metric(metric, catalog, mini_project)
    assert "口径为空" in result.special_rules
    assert result.grade in {"C", "D"}


def test_pinyin_detector_no_false_positive():
    """音节词典全分词：真拼音命中，英文单词不误判。"""
    roots = {"order", "monthly"}
    assert is_pinyin_token("xiaoshou", roots) is True
    assert is_pinyin_token("shouyi", roots) is True
    assert is_pinyin_token("monthly", roots) is False
    assert is_pinyin_token("order", roots) is False
    assert is_pinyin_token("amount", roots) is False


def test_load_scoring_rules_defaults():
    rules = load_scoring_rules()
    assert rules.total_max_score == 100
    assert rules.grade_for(96) == "S"
    assert rules.grade_for(85) == "A"
    assert rules.grade_for(70) == "B"
    assert rules.grade_for(60) == "C"
    assert rules.grade_for(40) == "D"


def test_score_and_persist_writes_files_and_history(mini_project: Path):
    first = score_and_persist(mini_project, "M_SALE_001", trigger="test")
    assert first.score_history and len(first.score_history) == 1

    path = mini_project / "scores" / "M_SALE_001.json"
    assert path.is_file()

    summary = mini_project / "scores" / "_summary.csv"
    assert summary.is_file()
    rows = load_summary(mini_project)
    assert any(r["metric_id"] == "M_SALE_001" for r in rows)

    # 再次评分 → 历史追加
    second = score_and_persist(mini_project, "M_SALE_001", trigger="test")
    assert len(second.score_history) == 2
    assert dim_score(second, "naming") >= 0


def test_load_score_missing_returns_none(mini_project: Path):
    assert load_score(mini_project, "M_NO_SUCH") is None
