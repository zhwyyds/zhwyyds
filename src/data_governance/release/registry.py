"""发布注册表 — 维护每个主题域的版本自增与发布历史。

版本号方案：按域自增整数，显示格式 v{n}（如 v1, v2）。
首次发布时从已有指标的 version 字段「播种」基线，避免覆盖手工历史。
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, cast


@dataclass
class ReleaseRecord:
    domain: str
    version: int
    version_label: str
    released_at: str
    note: str
    released_by: str
    metric_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _releases_path(base_dir: Path, domain: str) -> Path:
    return base_dir / "releases" / f"{domain}_releases.json"


def _parse_version_int(version: str) -> int:
    """从版本字符串提取整数（'1.0.0'->1, 'v2'->2, '3'->3）。"""
    m = re.search(r"(\d+)", version or "")
    return int(m.group(1)) if m else 0


class ReleaseRegistry:
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir

    def _load(self, domain: str) -> list[dict[str, Any]]:
        path = _releases_path(self._base_dir, domain)
        if not path.is_file():
            return []
        try:
            data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            return cast(list[dict[str, Any]], data.get("releases", []))
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, domain: str, releases: list[dict]) -> None:
        path = _releases_path(self._base_dir, domain)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"releases": releases}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def next_version(self, domain: str) -> int:
        """计算下一个版本号：已有发布历史与现有指标 version 取最大值 +1。"""
        releases = self._load(domain)
        max_from_releases = max((r.get("version", 0) for r in releases), default=0)

        # 从现有指标 version 播种基线
        max_from_metrics = 0
        from data_governance.io.catalog import load_catalog

        catalog = load_catalog(self._base_dir)
        for m in catalog.metrics:
            if m.domain_code == domain and m.version.strip():
                max_from_metrics = max(max_from_metrics, _parse_version_int(m.version))
        return max(max_from_releases, max_from_metrics) + 1

    def record_release(self, record: ReleaseRecord) -> ReleaseRecord:
        releases = self._load(record.domain)
        releases.append(record.to_dict())
        self._save(record.domain, releases)
        return record

    def list_releases(self, domain: str) -> list[ReleaseRecord]:
        return [ReleaseRecord(**r) for r in self._load(domain)]


def format_version(n: int) -> str:
    return f"v{n}"
