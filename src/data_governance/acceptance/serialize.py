from __future__ import annotations

from dataclasses import asdict
from typing import Any

from data_governance.acceptance.engine import AcceptanceReport


def acceptance_report_to_dict(report: AcceptanceReport) -> dict[str, Any]:
    return {
        "evaluated_at": report.evaluated_at,
        "metric_total": report.metric_total,
        "root_total": report.root_total,
        "total_points": report.total_points,
        "grade": report.grade,
        "veto": report.veto,
        "veto_reason": report.veto_reason,
        "skipped_notes": report.skipped_notes,
        "findings": [asdict(f) for f in report.findings],
        "dimensions": [
            {
                "name": d.name,
                "weight_label": d.weight_label,
                "max_points": d.max_points,
                "points": d.points,
                "passed": d.passed,
                "subscores": [asdict(s) for s in d.subscores],
            }
            for d in report.dimensions
        ],
    }
