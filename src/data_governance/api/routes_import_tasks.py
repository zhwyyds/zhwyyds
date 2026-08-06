"""批量指标导入 API（H31 P1）。

- POST /api/import-tasks/upload   CSV 上传 → 切分 → 生成待办任务
- GET  /api/import-tasks          任务列表
- GET  /api/import-tasks/{id}     任务详情
- POST /api/import-tasks/{id}/process   去重 + AI 生成（处理任务）
- POST /api/import-tasks/{id}/review   逐卡人工评审（通过→draft / 打回）
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import HTTPException

from data_governance.io.catalog import load_catalog
from data_governance.io.metrics_csv import batch_create_metrics
from data_governance.io.task_store import (
    create_import_tasks,
    dedup_rows,
    get_import_task,
    list_import_tasks,
    update_import_task,
)

# 打回后可编辑字段（人工评审修正范围）
EDITABLE_FIELDS = ("metric_cn", "caliber_desc", "unit", "frequency", "domain_code")

# AI 批量生成并发度（env AI_GENERATE_PARALLEL 可覆盖，默认 4 路）
AI_GENERATE_PARALLEL = max(1, int(os.environ.get("AI_GENERATE_PARALLEL", "4")))


def register(app, base: Path, metric_svc, ai_svc) -> None:
    @app.post("/api/import-tasks/upload")
    def import_tasks_upload(body: dict) -> dict:
        """CSV 上传 → 50 条/组切分 → 生成待办任务。"""
        csv_text = str((body or {}).get("csv") or "")
        if not csv_text.strip():
            raise HTTPException(400, "csv 内容为空")
        tasks = create_import_tasks(base, csv_text)
        if not tasks:
            raise HTTPException(400, "CSV 无有效数据行（需要 metric_cn 列）")
        return {"created": len(tasks), "tasks": tasks}

    @app.get("/api/import-tasks")
    def import_tasks_list() -> dict:
        return {"tasks": list_import_tasks(base)}

    def _safe_task(task_id: str) -> dict:
        """校验 task_id 安全并返回任务（非法/不存在 → 404）。"""
        from data_governance.io.task_store import task_path

        try:
            task_path(base, task_id)
        except ValueError:
            raise HTTPException(400, f"非法 task_id: {task_id!r}") from None
        task = get_import_task(base, task_id)
        if task is None:
            raise HTTPException(404, f"task not found: {task_id}")
        return task

    @app.get("/api/import-tasks/{task_id}")
    def import_task_detail(task_id: str) -> dict:
        return _safe_task(task_id)

    @app.post("/api/import-tasks/{task_id}/process")
    def import_task_process(task_id: str, body: dict | None = None) -> dict:
        """处理任务：去重比对 → 未通过项标记，新条目 AI 生成（存入 generated）。"""
        task = _safe_task(task_id)
        rows = task.get("generated") or []
        if not rows:
            raise HTTPException(400, "任务无数据行")

        catalog = load_catalog(base)
        result = dedup_rows(rows, catalog)

        # AI 生成新条目（并发调用 suggest_metric，pool.map 保持输入顺序；失败保留原始行标记 error）
        generated: list[dict] = []
        for row in result["dup"]:
            generated.append({**row, "_dedup": "dup", "_status": "skip"})
        for row in result["suspect"]:
            generated.append({**row, "_dedup": "suspect", "_status": "pending"})

        def _suggest_row(row: dict) -> dict:
            try:
                sug = ai_svc.suggest_metric(
                    {
                        "metric_cn": row.get("metric_cn", ""),
                        "caliber_desc": row.get("caliber_desc", ""),
                        "domain_code": row.get("domain_code", ""),
                        "unit": row.get("unit", ""),
                        "frequency": row.get("frequency", ""),
                    }
                )
                merged = {**row}
                for k in (
                    "metric_en",
                    "domain_code",
                    "unit",
                    "frequency",
                    "caliber_desc",
                    "category_l1",
                    "category_l2",
                ):
                    v = sug.get(k)
                    if v:
                        merged[k] = v
                merged["_dedup"] = "new"
                merged["_status"] = "pending"
                return merged
            except Exception as exc:
                return {**row, "_dedup": "new", "_status": "error", "_error": str(exc)[:200]}

        if result["new_rows"]:
            with ThreadPoolExecutor(max_workers=AI_GENERATE_PARALLEL) as pool:
                generated.extend(pool.map(_suggest_row, result["new_rows"]))

        updated = update_import_task(
            base,
            task_id,
            status="reviewing",
            dedup_result={
                "total": result["total"],
                "dup_count": result["dup_count"],
                "suspect_count": result["suspect_count"],
                "new_count": result["new_count"],
            },
            generated=generated,
            review_progress={"reviewed": 0, "approved": 0, "rejected": 0, "total": len(generated)},
        )
        assert updated is not None
        return updated

    @app.post("/api/import-tasks/{task_id}/review")
    def import_task_review(task_id: str, body: dict | None = None) -> dict:
        """逐卡人工评审：approve → 写入指标库 draft；reject → 标记打回。

        body: {row_index, action: "approve"|"reject", edits?: {...}}
        """
        task = _safe_task(task_id)
        body = body or {}
        row_index = int(body.get("row_index", -1))
        action = str(body.get("action") or "")
        if row_index < 0 or row_index >= len(task.get("generated") or []):
            raise HTTPException(400, "row_index 越界")
        if action not in ("approve", "reject"):
            raise HTTPException(400, "action 必须为 approve 或 reject")

        rows = list(task.get("generated") or [])
        row = dict(rows[row_index])

        # 打回：可带 edits 修正后标记 rejected，重提时再 approve
        if action == "reject":
            row["_status"] = "rejected"
            row["_reject_reason"] = str(body.get("reason") or "")[:200]
            rows[row_index] = row
        else:
            # 应用人工修正（如有）
            edits = body.get("edits") or {}
            if isinstance(edits, dict):
                for k, v in edits.items():
                    if k in EDITABLE_FIELDS and v is not None:
                        row[k] = str(v).strip()
            row["_status"] = "draft"
            row["_approved_at"] = __import__("data_governance.io.task_store", fromlist=["now_iso_cn"]).now_iso_cn()
            rows[row_index] = row
            # 写入指标库（draft 状态）
            payload = {
                "metric_id": row.get("metric_id") or "",
                "metric_cn": row.get("metric_cn", ""),
                "metric_en": row.get("metric_en", ""),
                "domain_code": row.get("domain_code", ""),
                "metric_type": "atomic",
                "caliber_desc": row.get("caliber_desc", ""),
                "unit": row.get("unit", ""),
                "frequency": row.get("frequency", ""),
                "category_l1": row.get("category_l1", ""),
                "category_l2": row.get("category_l2", ""),
                "review_status": "draft",
                "source_model": "batch_import",
            }
            try:
                batch_create_metrics(base, [payload])
            except Exception as exc:
                raise HTTPException(500, f"写入指标库失败: {exc}") from exc

        # 更新任务进度
        prog = dict(task.get("review_progress") or {})
        prog["reviewed"] = int(prog.get("reviewed", 0)) + 1
        if action == "approve":
            prog["approved"] = int(prog.get("approved", 0)) + 1
        else:
            prog["rejected"] = int(prog.get("rejected", 0)) + 1
        if int(prog.get("reviewed", 0)) >= int(prog.get("total", 0)):
            status = "done"
        else:
            status = task.get("status", "reviewing")

        updated = update_import_task(
            base,
            task_id,
            status=status,
            generated=rows,
            review_progress=prog,
        )
        assert updated is not None
        return updated
