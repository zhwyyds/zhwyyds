from pathlib import Path

import pytest


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _write_csv(path: Path, header: str, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


@pytest.fixture
def mini_project(tmp_path: Path, project_root: Path) -> Path:
    base = tmp_path / "gov"
    (base / "config").mkdir(parents=True)
    (base / "roots").mkdir()
    (base / "metrics").mkdir()
    (base / "lineage").mkdir()
    (base / "reviews" / "root_reviews").mkdir(parents=True)
    (base / "scoring").mkdir()
    (base / "config" / "domains.csv").write_text(
        (project_root / "config" / "domains.csv").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    models_src = project_root / "config" / "models.csv"
    if models_src.is_file():
        (base / "config" / "models.csv").write_text(
            models_src.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    root_header = (
        "root_id,root_cn,root_en,root_abbr,domain_code,root_type,description,"
        "source_model,review_status,created_at,updated_at"
    )
    _write_csv(
        base / "roots" / "sale_roots.csv",
        root_header,
        [
            "R_SALE_001,订单,order,ord,sale,noun,订单,model_consensus,approved,2026-08-03,2026-08-03",
            "R_TIME_001,月度,monthly,mon,base,time,月,model_consensus,approved,2026-08-03,2026-08-03",
        ],
    )

    metric_header = (
        "metric_id,metric_cn,metric_en,metric_abbr,domain_code,root_ids,metric_type,"
        "caliber_desc,unit,frequency,owner,source_model,review_status,created_at,updated_at"
    )
    _write_csv(
        base / "metrics" / "sale_metrics.csv",
        metric_header,
        [
            'M_SALE_001,月度销售额,monthly_sales_amt,mon_sal_amt,sale,"R_SALE_001;R_TIME_001",atomic,自然月内已完成订单的销售总金额,元,月,,model_consensus,approved,2026-08-03,2026-08-03',
        ],
    )
    return base
