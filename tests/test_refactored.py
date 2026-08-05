"""测试重构后的 Pydantic 请求模型与 Service 层。"""

from __future__ import annotations

from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from data_governance.api.app import create_app
from data_governance.api.schemas import MetricCreateRequest, MetricUpdateRequest
from data_governance.services import MetricService


class TestPydanticSchemas:
    """Pydantic 请求模型校验测试。"""

    def test_create_request_requires_metric_id(self):
        with pytest.raises(ValueError):
            MetricCreateRequest(metric_id="", metric_cn="test")

    def test_create_request_requires_metric_cn(self):
        with pytest.raises(ValueError):
            MetricCreateRequest(metric_id="M_SALE_001", metric_cn="")

    def test_create_request_defaults(self):
        req = MetricCreateRequest(metric_id="M_SALE_001", metric_cn="月度销售额")
        assert req.metric_type == "atomic"
        assert req.domain_code == ""
        assert req.unit == ""

    def test_update_request_all_optional(self):
        req = MetricUpdateRequest()
        assert req.caliber_desc is None
        assert req.owner is None

    def test_update_request_exclude_unset(self):
        req = MetricUpdateRequest(caliber_desc="新口径")
        payload = req.model_dump(exclude_unset=True, exclude_none=True)
        assert payload == {"caliber_desc": "新口径"}


class TestMetricService:
    """Service 层测试。"""

    def test_list_metrics(self, mini_project: Path):
        svc = MetricService(mini_project)
        metrics = svc.list_metrics()
        assert len(metrics) >= 1
        assert "metric_id" in metrics[0]

    def test_list_metrics_by_domain(self, mini_project: Path):
        svc = MetricService(mini_project)
        metrics = svc.list_metrics(domain="sale")
        assert all(m["domain_code"] == "sale" for m in metrics)

    def test_get_stats(self, mini_project: Path):
        svc = MetricService(mini_project)
        stats = svc.get_stats()
        assert stats["total"] >= 1
        assert "pending_review" in stats
        assert "published" in stats

    def test_find_record(self, mini_project: Path):
        svc = MetricService(mini_project)
        rec = svc.find_record("M_SALE_001")
        assert rec is not None
        assert rec.metric_cn == "月度销售额"

    def test_find_record_not_found(self, mini_project: Path):
        svc = MetricService(mini_project)
        assert svc.find_record("M_NONEXIST_001") is None

    def test_export_csv(self, mini_project: Path):
        svc = MetricService(mini_project)
        csv_text = svc.export_csv()
        assert "metric_id" in csv_text
        assert "M_SALE_001" in csv_text


class TestAPIValidation:
    """API 层 Pydantic 校验测试。"""

    @pytest.fixture
    def client(self, mini_project: Path) -> TestClient:
        return TestClient(create_app(mini_project))

    def test_create_metric_validation_error(self, client: TestClient):
        """空 metric_id 应返回 422 校验错误，而非 400。"""
        r = client.post("/api/metrics", json={"metric_cn": "测试"})
        assert r.status_code == 422

    def test_create_metric_success(self, client: TestClient):
        r = client.post(
            "/api/metrics",
            json={
                "metric_id": "M_SALE_002",
                "metric_cn": "季度营收",
                "metric_en": "quarterly_revenue",
                "caliber_desc": "季度营收总额",
            },
        )
        assert r.status_code == 200
        assert r.json()["metric_id"] == "M_SALE_002"

    def test_update_metric_partial(self, client: TestClient):
        """部分更新：只传需要改的字段。"""
        r = client.get("/api/metrics")
        mid = r.json()[0]["metric_id"]
        r = client.put(f"/api/metrics/{mid}", json={"owner": "数据团队"})
        assert r.status_code == 200
        assert r.json()["owner"] == "数据团队"

    def test_health_response_model(self, client: TestClient):
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "base_dir" in body

    def test_stats_response_model(self, client: TestClient):
        r = client.get("/api/metrics/stats")
        assert r.status_code == 200
        body = r.json()
        assert {"total", "pending_review", "published", "offline"} <= set(body.keys())


class TestCORSConfiguration:
    """CORS 配置测试。"""

    def test_cors_not_wildcard(self, mini_project: Path):
        """CORS 不再使用 allow_origins=['*']。"""
        import data_governance.api.middleware as mw

        origins = mw.get_cors_origins()
        assert "*" not in origins

    def test_cors_env_override(self, monkeypatch):
        monkeypatch.setenv("DATA_GOV_CORS_ORIGINS", "https://gov.example.com,https://staging.gov.example.com")
        import data_governance.api.middleware as mw

        origins = mw.get_cors_origins()
        assert "https://gov.example.com" in origins
        assert "https://staging.gov.example.com" in origins
