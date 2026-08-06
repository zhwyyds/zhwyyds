from pathlib import Path

from data_governance.acceptance.engine import run_acceptance


def test_acceptance_no_veto(mini_project: Path):
    report = run_acceptance(mini_project)
    assert report.veto is False
    assert report.metric_total == 1
    assert report.total_points > 0


def test_homonym_veto(tmp_path: Path, project_root: Path):
    base = tmp_path / "gov"
    base.mkdir()
    (base / "config").mkdir()
    (base / "roots").mkdir()
    (base / "metrics").mkdir()
    (base / "lineage").mkdir()
    (base / "config" / "domains.csv").write_text(
        "domain_code,domain_name_cn,domain_name_en,description,owner\nsale,交易,sale,,\n",
        encoding="utf-8",
    )
    metric_header = (
        "metric_id,metric_cn,metric_en,domain_code,root_ids,metric_type,"
        "caliber_desc,unit,frequency,owner,source_model,review_status,created_at,updated_at"
    )
    rows = "\n".join(
        [
            "M1,A,a_metric,sale,,atomic,口径甲,元,月,,manual,pending,2026-08-03,2026-08-03",
            "M2,B,a_metric,sale,,atomic,口径乙,元,月,,manual,pending,2026-08-03,2026-08-03",
        ]
    )
    csv_path = base / "metrics" / "sale_metrics.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_text(metric_header + "\n" + rows + "\n", encoding="utf-8")
    report = run_acceptance(base)
    assert report.veto is True
    assert report.grade == "C"
