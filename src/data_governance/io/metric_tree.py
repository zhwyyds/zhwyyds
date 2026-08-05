from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MetricTreeNode:
    node_id: str
    node_name: str
    node_type: str
    parent_id: str
    domain_code: str
    sort_order: int
    description: str = ""


def load_metric_tree(path: Path) -> list[MetricTreeNode]:
    if not path.is_file():
        return []
    nodes: list[MetricTreeNode] = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sort_raw = (row.get("sort_order") or "0").strip()
            try:
                sort_order = int(sort_raw)
            except ValueError:
                sort_order = 0
            nodes.append(
                MetricTreeNode(
                    node_id=(row.get("node_id") or "").strip(),
                    node_name=(row.get("node_name") or "").strip(),
                    node_type=(row.get("node_type") or "").strip(),
                    parent_id=(row.get("parent_id") or "").strip(),
                    domain_code=(row.get("domain_code") or "").strip(),
                    sort_order=sort_order,
                    description=(row.get("description") or "").strip(),
                )
            )
    nodes.sort(key=lambda n: (n.domain_code, n.sort_order, n.node_id))
    return nodes
