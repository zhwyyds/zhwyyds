"""数据自检 validate 模块测试（IT1-2）。"""

from pathlib import Path

from data_governance.cli import main
from data_governance.validation import ValidationIssue, validate_project

MINI_METRIC_HEADER = (
    "metric_id,metric_cn,metric_en,metric_abbr,domain_code,root_ids,metric_type,"
    "caliber_desc,unit,frequency,owner,source_model,review_status,created_at,updated_at"
)


def _errors(issues: list[ValidationIssue]) -> list[str]:
    return [i.message for i in issues if i.severity == "error"]


def test_validate_clean_mini_project(mini_project: Path):
    issues = validate_project(mini_project)
    assert _errors(issues) == [], f"mini_project 应无 error，实际: {issues}"


def test_validate_bad_field_count(mini_project: Path):
    metrics = mini_project / "metrics" / "sale_metrics.csv"
    metrics.write_text(
        metrics.read_text(encoding="utf-8")
        + "M_SALE_BAD,测试,test_bad,sale\n",
        encoding="utf-8",
    )
    issues = validate_project(mini_project)
    assert any("字段数" in m for m in _errors(issues))


def test_validate_missing_required(mini_project: Path):
    metrics = mini_project / "metrics" / "sale_metrics.csv"
    metrics.write_text(
        metrics.read_text(encoding="utf-8")
        + "M_SALE_901,,test_901,sale,,,,,,,,,,,\n",
        encoding="utf-8",
    )
    issues = validate_project(mini_project)
    assert any("metric_cn" in m for m in _errors(issues))


def test_validate_duplicate_id(mini_project: Path):
    metrics = mini_project / "metrics" / "sale_metrics.csv"
    metrics.write_text(
        metrics.read_text(encoding="utf-8")
        + "M_SALE_001,重复指标,dup_metric,,sale,,,,,,,,,,\n",
        encoding="utf-8",
    )
    issues = validate_project(mini_project)
    assert any("重复 ID: M_SALE_001" in m for m in _errors(issues))


def test_validate_bad_root_reference(mini_project: Path):
    metrics = mini_project / "metrics" / "sale_metrics.csv"
    metrics.write_text(
        metrics.read_text(encoding="utf-8")
        + "M_SALE_900,测试,test_ref,,sale,R_NO_SUCH,atomic,口径,元,月,,,approved,2026-08-05,2026-08-05\n",
        encoding="utf-8",
    )
    issues = validate_project(mini_project)
    assert any("引用未注册词根 R_NO_SUCH" in m for m in _errors(issues))


def test_validate_bad_domain_code(mini_project: Path):
    metrics = mini_project / "metrics" / "sale_metrics.csv"
    metrics.write_text(
        metrics.read_text(encoding="utf-8")
        + "M_SALE_902,测试,test_dom,,nope,,,,,,,,,,\n",
        encoding="utf-8",
    )
    issues = validate_project(mini_project)
    assert any("domain_code=nope" in m for m in _errors(issues))


def test_validate_bad_lineage_json(mini_project: Path):
    lineage = mini_project / "lineage" / "sale_lineage.json"
    lineage.write_text("{ not valid json", encoding="utf-8")
    issues = validate_project(mini_project)
    assert any("JSON 无法解析" in m for m in _errors(issues))


def test_cli_validate_clean_exit_0(mini_project: Path, capsys):
    # mini_project 只有 sale 域有数据，其余域报"缺文件"warning（不阻塞）
    assert main(["validate", "--base-dir", str(mini_project)]) == 0
    out = capsys.readouterr().out
    assert "0 error" in out


def test_cli_validate_dirty_exit_1(mini_project: Path, capsys):
    metrics = mini_project / "metrics" / "sale_metrics.csv"
    metrics.write_text(
        metrics.read_text(encoding="utf-8")
        + "M_SALE_903,测试,test_x,,sale,R_NO_SUCH,atomic,,,,,,,,\n",
        encoding="utf-8",
    )
    code = main(["validate", "--base-dir", str(mini_project)])
    assert code == 1
    out = capsys.readouterr().out
    assert "引用未注册词根" in out
