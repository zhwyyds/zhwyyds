"""版本发布控制模块 — 按域自增版本，批量发布 approved 指标。"""

from data_governance.release.registry import ReleaseRecord, ReleaseRegistry
from data_governance.release.service import publish_domain

__all__ = ["ReleaseRecord", "ReleaseRegistry", "publish_domain"]
