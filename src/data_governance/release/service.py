"""发布服务 — 按域批量发布 approved 指标，自动分配版本、记录历史。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from data_governance.io.catalog import load_catalog
from data_governance.io.metrics_csv import upsert_metric
from data_governance.release.registry import (
    ReleaseRecord,
    ReleaseRegistry,
    format_version,
)


def publish_domain(
    base_dir: Path,
    domain: str,
    *,
    note: str = "",
    released_by: str = "system",
) -> ReleaseRecord:
    """发布某主题域下所有 approved 指标。

    - 自动分配按域自增版本号 v{n}
    - 为每个指标写入 version 字段
    - 在 version_history 追加一行发布记录
    - 注册表记录本次发布（含指标清单、时间、备注）
    """
    catalog = load_catalog(base_dir)
    approved = [
        m for m in catalog.metrics
        if m.domain_code == domain and m.review_status == "approved"
    ]
    if not approved:
        raise ValueError(f"domain {domain!r} has no approved metrics to publish")

    # 发布门禁：口径草稿未核查（pending/rejected）禁止发布；"" 表示未进入口径流程（兼容存量）
    blocked = [m.metric_id for m in approved if m.caliber_status in ("pending", "rejected")]
    if blocked:
        raise ValueError(
            f"以下指标口径未核查，禁止发布: {', '.join(blocked)}（请先批准/修改口径）"
        )

    registry = ReleaseRegistry(base_dir)
    version = registry.next_version(domain)
    label = format_version(version)
    today = date.today().isoformat()

    metric_ids: list[str] = []
    for m in approved:
        history_parts = [p for p in m.version_history.split("|") if p.strip()]
        # 仅当末尾不是本次版本时才追加（幂等保护）
        new_history = f"{label}|{today}|{note or '批量发布'}"
        if history_parts and history_parts[-1].startswith(label):
            updated_history = m.version_history
        else:
            updated_history = f"{m.version_history};{new_history}" if m.version_history.strip() else new_history
        upsert_metric(
            base_dir,
            m.metric_id,
            {"version": label, "version_history": updated_history},
        )
        metric_ids.append(m.metric_id)

    record = ReleaseRecord(
        domain=domain,
        version=version,
        version_label=label,
        released_at=today,
        note=note,
        released_by=released_by,
        metric_ids=metric_ids,
    )
    registry.record_release(record)
    return record
