"""词根路由模块（R3 拆分）。

从 app.py 拆出：词根 CRUD / AI 建议 / 批量生成 / 评审入库 / 导入导出。
register(app, base, ai_svc) 由 create_app 装配。
"""

from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path

from fastapi import HTTPException, Query
from fastapi.responses import PlainTextResponse

from data_governance.config_loader import load_domains
from data_governance.io.catalog import load_catalog
from data_governance.schemas.roots import RootCreateRequest
from data_governance.services.ai_service import AiService


def register(app, base: Path, ai_svc: AiService) -> None:
    """注册词根路由（闭包风格，与拆分前行为一致）。"""

    @app.get("/api/roots")
    def list_roots(domain: str | None = Query(default=None)) -> list[dict]:
        catalog = load_catalog(base)
        rows = catalog.roots
        if domain:
            rows = [r for r in rows if r.domain_code == domain]
        return [asdict(r) for r in rows]

    @app.post("/api/roots")
    def create_root(body: RootCreateRequest) -> dict:
        """手工创建词根，自动分配 R_{DOMAIN}_{seq} ID（IT2-2）。"""
        from data_governance.io.roots_csv import (
            append_root_row,
            make_root_csv_row,
            roots_csv_path,
        )

        domain = body.domain_code.strip().lower()
        domains = load_domains(base / "config" / "domains.csv")
        if domain not in {d.domain_code for d in domains}:
            raise HTTPException(400, f"unknown domain: {domain}")

        path = roots_csv_path(base / "roots", domain)
        existing = load_catalog(base).roots
        if any(r.domain_code == domain and r.root_en == body.root_en for r in existing):
            raise HTTPException(400, f"root_en already exists in domain {domain}: {body.root_en}")

        row = make_root_csv_row(
            domain=domain,
            root_cn=body.root_cn,
            root_en=body.root_en,
            root_abbr=body.root_abbr or body.root_en,
            root_type=body.root_type,
            description=body.description,
            synonyms=body.synonyms,
            source_model=body.source_model,
            review_status=body.review_status,
            roots_dir=base / "roots",
        )
        append_root_row(path, row)
        return row.model_dump()

    @app.put("/api/roots/{root_id}")
    def update_root(root_id: str, body: dict) -> dict:
        """更新词根字段（IT2-2）。"""
        from data_governance.io.roots_csv import roots_csv_path, update_root_row

        catalog = load_catalog(base)
        target = next((r for r in catalog.roots if r.root_id == root_id), None)
        if target is None:
            raise HTTPException(404, f"root not found: {root_id}")

        path = roots_csv_path(base / "roots", target.domain_code)
        updated = update_root_row(path, root_id, body)
        if updated is None:
            raise HTTPException(404, f"root not found: {root_id}")
        return updated

    @app.post("/api/roots/suggest")
    def roots_suggest(body: dict) -> dict:
        """词根 AI 字段建议（逻辑在 AiService.suggest_root）。"""
        return ai_svc.suggest_root(body)

    @app.post("/api/roots/generate")
    def roots_generate(body: dict) -> dict:
        """词根 AI 批量生成（逻辑在 AiService.generate_roots）。"""
        return ai_svc.generate_roots(body)

    @app.post("/api/roots/generate/commit")
    def roots_generate_commit(body: dict) -> dict:
        """词根评审结果确认入库（逻辑在 AiService.commit_roots）。"""
        return ai_svc.commit_roots(body)

    @app.get("/api/roots/export")
    def export_roots(domain: str | None = Query(default=None)) -> PlainTextResponse:
        """词根导出 CSV（问题 6）。"""
        import io as _io

        from data_governance.io.roots_csv import ROOT_CSV_HEADER

        catalog = load_catalog(base)
        rows = [r for r in catalog.roots if not domain or r.domain_code == domain]
        buf = _io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=ROOT_CSV_HEADER)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: getattr(r, k, "") for k in ROOT_CSV_HEADER})
        return PlainTextResponse(
            content=buf.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="roots_export.csv"'},
        )

    @app.post("/api/roots/import")
    def import_roots(body: dict) -> dict:
        """词根导入：CSV 文本 → 校验 → 批量入库（问题 6）。"""
        import io as _io

        from data_governance.io.roots_csv import append_root_row, make_root_csv_row
        from data_governance.schemas.roots import ReviewStatus, RootType, SourceModel

        csv_text = str((body or {}).get("csv") or "")
        if not csv_text.strip():
            raise HTTPException(400, "csv 内容为空")
        rows = list(csv.DictReader(_io.StringIO(csv_text)))
        created, skipped = 0, 0
        errors: list[str] = []
        for row in rows:
            domain = str(row.get("domain_code") or "").strip().lower()
            root_cn = str(row.get("root_cn") or "").strip()
            root_en = str(row.get("root_en") or "").strip()
            if not domain or not root_cn or not root_en:
                skipped += 1
                continue
            if any(r.domain_code == domain and r.root_en == root_en for r in load_catalog(base).roots):
                skipped += 1
                continue
            try:
                record = make_root_csv_row(
                    domain=domain,
                    root_cn=root_cn,
                    root_en=root_en,
                    root_abbr=str(row.get("root_abbr") or "").strip() or root_en,
                    root_type=RootType(str(row.get("root_type") or "noun").strip() or "noun"),
                    description=str(row.get("description") or "").strip(),
                    source_model=SourceModel.manual,
                    review_status=ReviewStatus.pending,
                    roots_dir=base / "roots",
                )
                append_root_row(base / "roots" / f"{domain}_roots.csv", record)
                created += 1
            except Exception as exc:
                errors.append(f"{root_cn}: {exc}")
        return {"created": created, "skipped": skipped, "errors": errors}
