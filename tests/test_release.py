"""发布服务与版本注册表测试（IT1-1）。"""

from pathlib import Path

import pytest

from data_governance.io.catalog import load_catalog
from data_governance.release.registry import ReleaseRegistry, format_version
from data_governance.release.service import publish_domain


def test_format_version():
    assert format_version(1) == "v1"
    assert format_version(12) == "v12"


def test_next_version_starts_at_1(mini_project: Path):
    reg = ReleaseRegistry(mini_project)
    assert reg.next_version("sale") == 1


def test_publish_domain_assigns_version(mini_project: Path):
    record = publish_domain(mini_project, "sale", note="IT1 测试发布")
    assert record.version == 1
    assert record.version_label == "v1"
    assert record.metric_ids == ["M_SALE_001"]
    assert record.note == "IT1 测试发布"

    # CSV 已写入 version 与历史
    catalog = load_catalog(mini_project)
    m = next(x for x in catalog.metrics if x.metric_id == "M_SALE_001")
    assert m.version == "v1"
    assert "v1" in m.version_history

    # 注册表持久化到 releases/{domain}_releases.json
    reg = ReleaseRegistry(mini_project)
    releases = reg.list_releases("sale")
    assert len(releases) == 1
    assert releases[0].version == 1
    assert releases[0].version_label == "v1"


def test_second_publish_increments_version(mini_project: Path):
    publish_domain(mini_project, "sale")
    record = publish_domain(mini_project, "sale")
    assert record.version == 2
    assert record.version_label == "v2"

    catalog = load_catalog(mini_project)
    m = next(x for x in catalog.metrics if x.metric_id == "M_SALE_001")
    assert m.version == "v2"
    # 历史不因重复发布而追加重复版本
    history = m.version_history
    assert history.count("v1|") == 1


def test_publish_no_approved_raises(mini_project: Path):
    with pytest.raises(ValueError):
        publish_domain(mini_project, "cust")


def test_release_registry_roundtrip(mini_project: Path):
    reg = ReleaseRegistry(mini_project)
    assert reg.list_releases("sale") == []
    publish_domain(mini_project, "sale")
    reloaded = ReleaseRegistry(mini_project)
    releases = reloaded.list_releases("sale")
    assert len(releases) == 1
    assert releases[0].metric_ids == ["M_SALE_001"]
