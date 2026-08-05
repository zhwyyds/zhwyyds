"""黄金演示数据脚本测试（IT3-3）。"""

import subprocess
import sys
from pathlib import Path

from data_governance.io.catalog import load_catalog


def _mini_project(tmp_path: Path) -> Path:
    """搭建最小项目结构（domains + sale 词根）。"""
    base = tmp_path / "gov"
    (base / "config").mkdir(parents=True)
    (base / "roots").mkdir()
    (base / "config" / "domains.csv").write_text(
        "domain_code,domain_name_cn,domain_name_en,description,owner\nsale,交易,sale,订单支付退款,\n",
        encoding="utf-8",
    )
    (base / "roots" / "sale_roots.csv").write_text(
        "root_id,root_cn,root_en,root_abbr,domain_code,root_type,description,source_model,review_status,created_at,updated_at\n"
        "R_SALE_001,订单,order,ord,sale,noun,订单,model_consensus,approved,2026-08-05,2026-08-05\n",
        encoding="utf-8",
    )
    return base


def test_demo_data_generates_four_metrics(tmp_path: Path, project_root: Path):
    base = _mini_project(tmp_path)
    script = project_root / "scripts" / "demo_data.py"
    result = subprocess.run(
        [sys.executable, str(script), "--base-dir", str(base)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "created=4" in result.stdout

    ids = {m.metric_id for m in load_catalog(base).metrics}
    assert {"M_SALE_D01", "M_SALE_D02", "M_SALE_D03", "M_SALE_D04"} <= ids


def test_demo_data_idempotent(tmp_path: Path, project_root: Path):
    base = _mini_project(tmp_path)
    script = project_root / "scripts" / "demo_data.py"
    subprocess.run([sys.executable, str(script), "--base-dir", str(base)], check=True, timeout=60)
    result = subprocess.run(
        [sys.executable, str(script), "--base-dir", str(base)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert "created=0" in result.stdout
    assert "skipped=4" in result.stdout
