"""指标 Service — 封装指标相关的业务逻辑。"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from data_governance.io.catalog import MetricRecord, load_catalog
from data_governance.io.metrics_csv import (
    create_metric,
    export_metrics_csv,
    metric_stats,
    upsert_metric,
)


class MetricService:
    """指标业务服务层，封装 CRUD + 统计 + 导出。"""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir

    def list_metrics(self, domain: str | None = None) -> list[dict]:
        """查询指标列表，可选按域过滤，返回 dict 列表。"""
        catalog = load_catalog(self._base_dir)
        rows = catalog.metrics
        if domain:
            rows = [m for m in rows if m.domain_code == domain]
        return [asdict(m) for m in rows]

    def get_stats(self) -> dict[str, int]:
        """指标统计。"""
        catalog = load_catalog(self._base_dir)
        return metric_stats(catalog.metrics)

    def create(self, payload: dict) -> dict:
        """创建指标，返回 dict。"""
        rec = create_metric(self._base_dir, payload)
        return asdict(rec)

    def update(self, metric_id: str, payload: dict) -> dict:
        """更新指标，返回 dict。"""
        rec = upsert_metric(self._base_dir, metric_id, payload)
        return asdict(rec)

    def export_csv(self) -> str:
        """导出全量指标 CSV。"""
        return export_metrics_csv(self._base_dir)

    def find_record(self, metric_id: str) -> MetricRecord | None:
        """按 ID 查找单条指标记录。"""
        catalog = load_catalog(self._base_dir)
        return next((m for m in catalog.metrics if m.metric_id == metric_id), None)
