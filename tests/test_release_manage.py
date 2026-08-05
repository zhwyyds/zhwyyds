"""发布撤销/版本对比/跨域总览测试（IT3-1）。"""

from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from data_governance.api.app import create_app
from data_governance.io.catalog import load_catalog
from data_governance.release.service import (
    publish_domain,
    release_overview,
    revert_release,
    version_diff,
)


def _two_releases(mini_project: Path) -> tuple[Path, int]:
    publish_domain(mini_project, "sale", note="v1 首版")
    publish_domain(mini_project, "sale", note="v2 新增指标")
    return mini_project, 2


def test_revert_rolls_back_version(mini_project: Path):
    base = _two_releases(mini_project)[0]
    result = revert_release(base, "sale", 2, note="口径修正")
    assert result["status"] == "revoked"
    assert result["rolled_back_to"] == "v1"

    m = next(x for x in load_catalog(base).metrics if x.metric_id == "M_SALE_001")
    assert m.version == "v1"
    assert "revoked_v2" in m.version_history


def test_revert_marks_registry(mini_project: Path):
    base = _two_releases(mini_project)[0]
    revert_release(base, "sale", 2)
    # 再次撤销同一版本应报错
    with pytest.raises(ValueError, match="已撤销"):
        revert_release(base, "sale", 2)


def test_revert_unknown_version_raises(mini_project: Path):
    publish_domain(mini_project, "sale")
    with pytest.raises(ValueError, match="无 v9 发布记录"):
        revert_release(mini_project, "sale", 9)


def test_version_diff(mini_project: Path):
    base = _two_releases(mini_project)[0]
    diff = version_diff(base, "sale", "v1", "v2")
    assert diff["added"] == []  # 同一指标重复发布，无新增
    assert diff["removed"] == []
    assert diff["unchanged"] == 1


def test_release_overview(mini_project: Path):
    assert release_overview(mini_project) == []  # 未发布
    publish_domain(mini_project, "sale", note="首版")
    overview = release_overview(mini_project)
    assert len(overview) == 1
    row = overview[0]
    assert row["domain"] == "sale"
    assert row["latest_version"] == "v1"
    assert row["revoked"] is False


@pytest.fixture
def api_client(mini_project: Path) -> TestClient:
    return TestClient(create_app(mini_project))


def test_api_revert_flow(api_client: TestClient, mini_project: Path):
    publish_domain(mini_project, "sale")
    publish_domain(mini_project, "sale")
    r = api_client.post("/api/domains/sale/revert", json={"version": 2, "note": "测试撤销"})
    assert r.status_code == 200
    assert r.json()["status"] == "revoked"

    r = api_client.get("/api/domains/sale/version-diff?from=v1&to=v2")
    assert r.status_code == 200
    assert "added" in r.json()

    r = api_client.get("/api/releases/overview")
    assert any(x["domain"] == "sale" and x["revoked"] for x in r.json())


def test_api_revert_requires_version(api_client: TestClient):
    r = api_client.post("/api/domains/sale/revert", json={})
    assert r.status_code == 400
