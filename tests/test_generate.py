"""批量生成测试（IT2-1）。"""

import shutil
from pathlib import Path

from data_governance.generate import generate_derived_metrics, load_modifiers
from data_governance.io.catalog import load_catalog


def _with_modifiers(mini_project: Path, project_root: Path) -> Path:
    """把真实 modifier_rules.csv 复制进 mini_project。"""
    src = project_root / "config" / "modifier_rules.csv"
    if src.is_file():
        shutil.copy(src, mini_project / "config" / "modifier_rules.csv")
    return mini_project


def test_load_modifiers(mini_project: Path, project_root: Path):
    mods = load_modifiers(_with_modifiers(mini_project, project_root))
    assert len(mods) >= 4
    by_id = {m.modifier_id: m for m in mods}
    assert by_id["T001"].modifier_en == "mtd"
    assert by_id["T001"].modifier_type == "time"


def test_generate_derived_dry_run(mini_project: Path, project_root: Path):
    base = _with_modifiers(mini_project, project_root)
    result = generate_derived_metrics(base, ["M_SALE_001"], ["T001", "T002"], dry_run=True)
    assert result.dry_run is True
    assert len(result.generated) == 2
    ens = {m.metric_en for m in result.generated}
    assert "mtd_monthly_sales_amt" in ens
    assert "ytd_monthly_sales_amt" in ens
    # dry-run 不落盘
    assert len(load_catalog(base).metrics) == 1


def test_generate_derived_writes_and_idempotent(mini_project: Path, project_root: Path):
    base = _with_modifiers(mini_project, project_root)
    result = generate_derived_metrics(base, ["M_SALE_001"], ["T001", "T002"], dry_run=False)
    assert len(result.generated) == 2
    assert result.invalid_atomics == [] and result.invalid_modifiers == []

    catalog = load_catalog(base)
    assert len(catalog.metrics) == 3
    derived = [m for m in catalog.metrics if m.metric_type == "derived"]
    assert len(derived) == 2
    m = derived[0]
    assert m.review_status == "pending"
    assert "本月" in m.metric_cn or "本年" in m.metric_cn

    # 幂等：再跑一次，已存在跳过
    again = generate_derived_metrics(base, ["M_SALE_001"], ["T001", "T002"], dry_run=False)
    assert again.generated == []
    assert len(again.existing) == 2
    assert len(load_catalog(base).metrics) == 3


def test_generate_invalid_atomic_and_modifier(mini_project: Path, project_root: Path):
    base = _with_modifiers(mini_project, project_root)
    result = generate_derived_metrics(base, ["M_NO_SUCH"], ["T001"], dry_run=True)
    assert result.invalid_atomics == ["M_NO_SUCH"]
    assert result.generated == []

    result2 = generate_derived_metrics(base, ["M_SALE_001"], ["T999"], dry_run=True)
    assert result2.invalid_modifiers == ["T999"]
    assert result2.generated == []


def test_generate_assigns_next_metric_id(mini_project: Path, project_root: Path):
    base = _with_modifiers(mini_project, project_root)
    result = generate_derived_metrics(base, ["M_SALE_001"], ["T001"], dry_run=False)
    assert result.generated[0].metric_id == "M_SALE_002"
