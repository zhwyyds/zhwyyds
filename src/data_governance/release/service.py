"""发布服务 — 按域批量发布 approved 指标，自动分配版本、记录历史。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from data_governance.config_loader import load_domains
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


def _parse_label(label: str) -> int:
    """'v2' -> 2。"""
    return int(str(label).lstrip("v") or 0)


def revert_release(
    base_dir: Path,
    domain: str,
    version: int,
    *,
    note: str = "",
    released_by: str = "system",
) -> dict:
    """撤销指定版本：指标 version 回退上一版本，history 留痕，registry 标记 revoked（IT3-1）。"""
    registry = ReleaseRegistry(base_dir)
    raw = [r for r in registry._load(domain) if r.get("version") == version]
    if not raw:
        raise ValueError(f"domain {domain!r} 无 v{version} 发布记录")
    if raw[0].get("status") == "revoked":
        raise ValueError(f"v{version} 已撤销，不可重复撤销")

    prev_label = format_version(version - 1) if version > 1 else ""
    today = date.today().isoformat()
    catalog = load_catalog(base_dir)
    metric_ids = raw[0].get("metric_ids") or []
    for mid in metric_ids:
        m = next((x for x in catalog.metrics if x.metric_id == mid), None)
        if m is None:
            continue
        revoked_note = f"revoked_v{version}|{today}|{note or '撤销发布'}"
        history = f"{m.version_history};{revoked_note}" if m.version_history.strip() else revoked_note
        upsert_metric(
            base_dir,
            mid,
            {"version": prev_label, "version_history": history},
        )

    raw[0]["status"] = "revoked"
    raw[0]["revoked_at"] = today
    raw[0]["revoke_note"] = note
    raw[0]["revoked_by"] = released_by
    registry._save(domain, raw)
    return {
        "domain": domain,
        "version": version,
        "version_label": format_version(version),
        "status": "revoked",
        "rolled_back_to": prev_label or "（无上一版本）",
        "metric_ids": metric_ids,
        "revoked_at": today,
    }


def version_diff(base_dir: Path, domain: str, from_label: str, to_label: str) -> dict:
    """对比两个发布版本包含的指标差异：added = to 独有，removed = from 独有（IT3-1）。"""
    registry = ReleaseRegistry(base_dir)
    releases = registry.list_releases(domain)

    def ids_for(label: str) -> set[str]:
        v = _parse_label(label)
        record = next((r for r in releases if r.version == v), None)
        return set(record.metric_ids) if record else set()

    old_ids, new_ids = ids_for(from_label), ids_for(to_label)
    return {
        "domain": domain,
        "from": from_label,
        "to": to_label,
        "added": sorted(new_ids - old_ids),
        "removed": sorted(old_ids - new_ids),
        "unchanged": len(old_ids & new_ids),
    }


def release_overview(base_dir: Path) -> list[dict]:
    """跨域发布总览：每域发布次数、最新版本、最近发布时间、是否已撤销（IT3-1）。"""
    domains = load_domains(base_dir / "config" / "domains.csv")
    out: list[dict] = []
    for d in domains:
        releases = ReleaseRegistry(base_dir).list_releases(d.domain_code)
        if not releases:
            continue
        latest = max(releases, key=lambda r: r.version)
        out.append(
            {
                "domain": d.domain_code,
                "domain_name": d.domain_name_cn,
                "total_releases": len(releases),
                "latest_version": latest.version_label,
                "latest_at": latest.released_at,
                "latest_note": latest.note,
                "revoked": latest.status == "revoked",
            }
        )
    return sorted(out, key=lambda x: x["domain"])
