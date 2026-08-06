"""批量导入待办任务存储与处理（H31 P1）。

任务实体（落盘 tasks/ 目录）：
    task_id / batch_id / group_no / total_rows / status
    / dedup_result / generated / review_progress / created_at

状态机：pending → processing（去重+AI生成）→ reviewing（人工评审）→ done
"""
from __future__ import annotations

import csv
import io
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# 每组合并条数（用户确认 50 条/组）
GROUP_SIZE = 50

TASK_STATUS = ("pending", "processing", "reviewing", "done")


@dataclass
class ImportTask:
    task_id: str
    batch_id: str
    group_no: int
    total_rows: int
    status: str = "pending"
    dedup_result: dict = field(default_factory=dict)
    generated: list[dict] = field(default_factory=list)
    review_progress: dict = field(default_factory=lambda: {"reviewed": 0, "approved": 0, "rejected": 0})
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "batch_id": self.batch_id,
            "group_no": self.group_no,
            "total_rows": self.total_rows,
            "status": self.status,
            "dedup_result": self.dedup_result,
            "generated": self.generated,
            "review_progress": self.review_progress,
            "created_at": self.created_at,
        }


def now_iso_cn() -> str:
    """中国时区 ISO 时间（与 reviews.py 保持一致）。"""
    from datetime import timedelta, timezone

    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")


def tasks_dir(base_dir: Path) -> Path:
    d = base_dir / "tasks"
    d.mkdir(parents=True, exist_ok=True)
    return d


def task_path(base_dir: Path, task_id: str) -> Path:
    return tasks_dir(base_dir) / f"{task_id}.json"


def _load_task(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        data: dict = json.load(f)
    return data


def _save_task(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def split_csv(csv_text: str, *, group_size: int = GROUP_SIZE) -> list[list[dict]]:
    """CSV 文本 → 按 group_size 切分为组，每组是 dict 列表。

    返回 [ [row, ...], ... ]；空行/缺 metric_cn 的行跳过。
    """
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    clean = []
    for row in rows:
        cn = str(row.get("metric_cn") or "").strip()
        if not cn:
            continue
        clean.append({k: (v or "").strip() if isinstance(v, str) else v for k, v in row.items()})
    return [clean[i : i + group_size] for i in range(0, len(clean), group_size)]


def _cn_normalize(s: str) -> str:
    """中文名归一化：去空白、去括号内容、去常见后缀词。"""
    s = re.sub(r"[（(].*?[）)]", "", s)
    s = re.sub(r"\s+", "", s)
    for suffix in ("指标", "总额", "总量", "数量", "金额", "数"):
        if s.endswith(suffix) and len(s) > len(suffix):
            s = s[: -len(suffix)]
            break
    return s


def _metric_cn_set(catalog) -> set[str]:
    """指标库中文名归一化集合（用于精确 + 近似去重）。"""
    names = {m.metric_cn.strip() for m in catalog.metrics if m.metric_cn.strip()}
    norm = {_cn_normalize(n) for n in names if n}
    return names | norm


def dedup_rows(rows: list[dict], catalog) -> dict:
    """去重比对：返回 {total, dup, suspect, new_rows}。

    - 精确匹配：metric_cn 与库内完全一致 → dup
    - 近似匹配：归一化后命中 → suspect（标记，不自动丢弃）
    - 其余 → new_rows（进入 AI 生成）
    """
    existing = _metric_cn_set(catalog)
    dup: list[dict] = []
    suspect: list[dict] = []
    new_rows: list[dict] = []
    for row in rows:
        cn = str(row.get("metric_cn") or "").strip()
        if not cn:
            continue
        if cn in existing:
            dup.append(row)
        elif _cn_normalize(cn) in existing:
            suspect.append(row)
        else:
            new_rows.append(row)
    return {
        "total": len(rows),
        "dup": dup,
        "suspect": suspect,
        "new_rows": new_rows,
        "dup_count": len(dup),
        "suspect_count": len(suspect),
        "new_count": len(new_rows),
    }


def create_import_tasks(base_dir: Path, csv_text: str, batch_id: str | None = None) -> list[dict]:
    """CSV 切分 → 每组生成一个待办任务，落盘。返回任务 dict 列表。"""
    groups = split_csv(csv_text)
    if not groups:
        return []
    batch = batch_id or datetime.now().strftime("%Y%m%d%H%M%S")
    created: list[dict] = []
    for idx, group in enumerate(groups, start=1):
        task = ImportTask(
            task_id=f"T{batch}_{idx:03d}",
            batch_id=batch,
            group_no=idx,
            total_rows=len(group),
            status="pending",
            created_at=now_iso_cn(),
        )
        # 初始 generated 用原始行占位（含去重前信息），去重在 processing 阶段执行
        task.generated = group
        path = task_path(base_dir, task.task_id)
        _save_task(path, task.to_dict())
        created.append(task.to_dict())
    return created


def list_import_tasks(base_dir: Path) -> list[dict]:
    """列出全部任务（按创建时间倒序）。"""
    out = []
    for p in sorted(tasks_dir(base_dir).glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            out.append(_load_task(p))
        except (json.JSONDecodeError, OSError):
            continue
    return out


def get_import_task(base_dir: Path, task_id: str) -> dict | None:
    p = task_path(base_dir, task_id)
    if not p.is_file():
        return None
    return _load_task(p)


def update_import_task(base_dir: Path, task_id: str, **fields) -> dict | None:
    p = task_path(base_dir, task_id)
    if not p.is_file():
        return None
    data = _load_task(p)
    data.update(fields)
    _save_task(p, data)
    return data


def new_task_id() -> str:
    return f"T{uuid.uuid4().hex[:8]}"
