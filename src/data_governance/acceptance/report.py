from __future__ import annotations

from data_governance.acceptance.engine import AcceptanceReport


def render_markdown(report: AcceptanceReport) -> str:
    lines: list[str] = [
        "# 数据治理项目验收评分报告",
        "",
        "## 基本信息",
        f"- 评估日期：{report.evaluated_at}",
        f"- 评估范围：{len(report.catalog.domains)} 个主题域",
        f"- 指标总数：{report.metric_total}",
        f"- 词根总数：{report.root_total}",
        "",
        "## 评分汇总",
        "",
        "| 维度 | 权重 | 得分 | 达标 |",
        "|------|------|------|------|",
    ]

    for dim in report.dimensions:
        mark = "✅" if dim.passed else "❌"
        lines.append(f"| {dim.name} | {dim.weight_label} | {dim.points:.1f}/{dim.max_points:.0f} | {mark} |")

    veto_mark = "（一票否决）" if report.veto else ""
    lines.extend(
        [
            f"| **总分** | 100% | **{report.total_points:.1f}** | **{report.grade}** {veto_mark} |",
            "",
            "## 维度明细",
        ]
    )

    for dim in report.dimensions:
        lines.append(f"### {dim.name}")
        for sub in dim.subscores:
            auto = "" if sub.automated else "（未自动评估）"
            lines.append(f"- {sub.name}：{sub.points:.1f}/{sub.max_points:.0f} — {sub.detail}{auto}")
        lines.append("")

    homonym = next(
        (s for d in report.dimensions if d.name == "同名同义" for s in d.subscores if s.name == "同名异义检查"), None
    )
    synonym = next(
        (s for d in report.dimensions if d.name == "同名同义" for s in d.subscores if s.name == "同义异名检查"), None
    )
    lines.extend(
        [
            "## 同名同义检查结果",
            f"- 同名异义：{homonym.detail if homonym else '—'} {'❌ 一票否决' if report.veto else '✅'}",
            f"- 同义异名：{synonym.detail if synonym else '—'}",
            "",
            "## 未自动评估项",
        ]
    )
    for note in report.skipped_notes:
        lines.append(f"- {note}")

    if report.findings:
        lines.extend(["", "## 不达标项及整改建议"])
        for i, f in enumerate(report.findings, 1):
            lines.append(f"{i}. [{f.severity}] {f.message}")

    conclusion = "不通过"
    if report.veto:
        conclusion = "不通过（同名异义一票否决）"
    elif report.grade in ("S", "A"):
        conclusion = "通过"
    elif report.grade == "B":
        conclusion = "整改后复核"
    else:
        conclusion = "不通过"

    lines.extend(["", "## 验收结论", conclusion, ""])
    return "\n".join(lines)
