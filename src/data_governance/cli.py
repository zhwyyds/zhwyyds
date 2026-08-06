from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from data_governance.acceptance.engine import run_acceptance
from data_governance.acceptance.report import render_markdown
from data_governance.llm.bootstrap import bootstrap_llm_env
from data_governance.paths import repo_root
from data_governance.pipeline.metric_review import MetricReviewPipeline
from data_governance.pipeline.root_generation import RootGenerationPipeline
from data_governance.schemas.metrics import MetricReviewRequest
from data_governance.schemas.roots import RootGenerationRequest
from data_governance.validation import validate_project


def main(argv: list[str] | None = None) -> int:
    """CLI 入口：serve / validate / generate / review / caliber 等子命令分发。"""
    parser = argparse.ArgumentParser(prog="data-governance")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("version", help="Print package version")

    root_p = sub.add_parser("root", help="词根相关命令")
    root_sub = root_p.add_subparsers(dest="root_command")

    gen = root_sub.add_parser("generate", help="多模型词根生成（Mock / M3 Live）")
    gen.add_argument("--domain", required=True, help="主题域代码，如 cust")
    gen.add_argument("--input", required=True, type=Path, help="输入 JSON（§2.1）")
    gen.add_argument(
        "--live",
        action="store_true",
        help="强制调用真实 LLM（需至少 2 个模型 API Key；等同 DATA_GOV_LLM_MODE=live）",
    )
    gen.add_argument(
        "--write-roots",
        action="store_true",
        help="自动通过项写入 roots/{domain}_roots.csv",
    )
    gen.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help="项目根目录（默认自动查找 config/domains.csv）",
    )

    metric_p = sub.add_parser("metric", help="指标相关命令")
    metric_sub = metric_p.add_subparsers(dest="metric_command")

    mrev = metric_sub.add_parser("review", help="多模型指标评审（Mock / M3 Live）")
    mrev.add_argument("--domain", required=True, help="主题域代码，如 sale")
    mrev.add_argument("--input", required=True, type=Path, help="输入 JSON（§3.1）")
    mrev.add_argument(
        "--live",
        action="store_true",
        help="强制调用真实 LLM（需至少 2 个模型 API Key）",
    )
    mrev.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help="项目根目录（默认自动查找 config/domains.csv）",
    )

    mgen = metric_sub.add_parser("generate", help="批量生成派生指标（原子×修饰词）")
    mgen.add_argument("--domain", required=True, help="主题域代码，如 sale")
    mgen.add_argument("--atomics", required=True, help="逗号分隔的原子指标 ID，如 M_SALE_001,M_SALE_002")
    mgen.add_argument("--modifiers", required=True, help="逗号分隔的修饰词 ID，如 T001,T002")
    mgen.add_argument("--write", action="store_true", help="写入指标库（默认 dry-run 预览）")
    mgen.add_argument("--base-dir", type=Path, default=None)

    acc_p = sub.add_parser("acceptance", help="项目验收评分（M5）")
    acc_sub = acc_p.add_subparsers(dest="acceptance_command")
    acc_run = acc_sub.add_parser("run", help="扫描数据目录并生成验收报告")
    acc_run.add_argument("--base-dir", type=Path, default=None)
    acc_run.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Markdown 报告路径（默认 scoring/acceptance_report_YYYY-MM-DD.md）",
    )
    acc_run.add_argument("--json", action="store_true", help="同时输出 JSON 摘要到 stdout")

    serve_p = sub.add_parser("serve", help="启动本地 HTTP API（M4）")
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=8765)
    serve_p.add_argument("--base-dir", type=Path, default=None)

    val_p = sub.add_parser("validate", help="数据自检：扫描 roots/metrics/lineage 完整性")
    val_p.add_argument("--base-dir", type=Path, default=None)

    args = parser.parse_args(argv)
    if args.command == "version":
        from data_governance import __version__

        print(__version__)
        return 0

    if args.command == "root" and args.root_command == "generate":
        base = args.base_dir or repo_root()
        bootstrap_llm_env(base)
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        request = RootGenerationRequest.model_validate(payload)
        if request.domain != args.domain:
            print("warning: --domain 与 JSON domain 不一致，以 CLI --domain 为准", file=sys.stderr)
            request = request.model_copy(update={"domain": args.domain})
        use_mock = False if args.live else None
        pipe = RootGenerationPipeline(base_dir=base, use_mock=use_mock)
        doc = pipe.run(request, write_roots=args.write_roots)
        approved = sum(1 for i in doc.items if i.auto_approved)
        pending = len(doc.items) - approved
        print(f"review_id={doc.review_id} items={len(doc.items)} approved={approved} pending={pending}")
        return 0

    if args.command == "metric" and args.metric_command == "review":
        base = args.base_dir or repo_root()
        bootstrap_llm_env(base)
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        m_request = MetricReviewRequest.model_validate(payload)
        if m_request.domain != args.domain:
            print("warning: --domain 与 JSON domain 不一致，以 CLI --domain 为准", file=sys.stderr)
            m_request = m_request.model_copy(update={"domain": args.domain})
        use_mock = False if args.live else None
        m_doc = MetricReviewPipeline(base_dir=base, use_mock=use_mock).run(m_request)
        approved = sum(1 for i in m_doc.items if i.final_decision.approved)
        pending = len(m_doc.items) - approved
        print(f"review_id={m_doc.review_id} items={len(m_doc.items)} approved={approved} pending={pending}")
        return 0

    if args.command == "metric" and args.metric_command == "generate":
        from data_governance.generate import generate_derived_metrics

        base = args.base_dir or repo_root()
        atomics = [x.strip() for x in args.atomics.split(",") if x.strip()]
        modifiers = [x.strip() for x in args.modifiers.split(",") if x.strip()]
        result = generate_derived_metrics(base, atomics, modifiers, dry_run=not args.write)
        mode = "dry-run（未写盘）" if result.dry_run else "已写入"
        print(
            f"generate: 生成 {len(result.generated)} 个（{mode}）"
            f" 已存在跳过 {len(result.existing)}"
            f" 无效原子 {len(result.invalid_atomics)}"
            f" 无效修饰词 {len(result.invalid_modifiers)}"
        )
        for m in result.generated:
            print(f"  {m.metric_id}  {m.metric_cn}  {m.metric_en}")
        return 0

    if args.command == "acceptance" and args.acceptance_command == "run":
        from datetime import date

        base = args.base_dir or repo_root()
        report = run_acceptance(base)
        out = args.output or (base / "scoring" / f"acceptance_report_{date.today().isoformat()}.md")
        out.parent.mkdir(parents=True, exist_ok=True)
        md = render_markdown(report)
        out.write_text(md, encoding="utf-8")
        print(f"total={report.total_points:.1f} grade={report.grade} veto={report.veto} report={out}")
        if args.json:
            summary = {
                "total": report.total_points,
                "grade": report.grade,
                "veto": report.veto,
                "metrics": report.metric_total,
                "roots": report.root_total,
                "dimensions": [
                    {"name": d.name, "points": d.points, "max": d.max_points, "passed": d.passed}
                    for d in report.dimensions
                ],
            }
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    if args.command == "serve":
        try:
            import uvicorn
        except ImportError:
            print("请安装 API 依赖: pip install -e '.[api]'", file=sys.stderr)
            return 1
        base = args.base_dir or repo_root()
        bootstrap_llm_env(base)
        os.environ["DATA_GOV_BASE_DIR"] = str(base.resolve())
        from data_governance.api.app import create_app

        api = create_app(base)
        print(f"Serving {base} at http://{args.host}:{args.port}/ (docs: /docs)")
        uvicorn.run(api, host=args.host, port=args.port, log_level="info")
        return 0

    if args.command == "validate":
        base = args.base_dir or repo_root()
        issues = validate_project(base)
        if not issues:
            print("validate: OK — 未发现问题")
            return 0
        for i in issues:
            print(f"[{i.severity.upper():7}] {i.file}: {i.message}")
        errors = sum(1 for i in issues if i.severity == "error")
        print(f"validate: 共 {len(issues)} 个问题（{errors} error / {len(issues) - errors} warning）")
        return 1 if errors else 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
