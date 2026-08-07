"""API 企业级规范测试：统一错误响应 + 幂等保护（A 批改造）。"""

import pytest
from fastapi.testclient import TestClient

from data_governance.api.app import create_app


@pytest.fixture
def client(mini_project):
    app = create_app(mini_project)
    with TestClient(app) as c:
        yield c


def _upload(client, name: str = "错误码测试指标") -> str:
    import io

    buf = io.StringIO()
    buf.write("metric_cn,caliber_desc\n")
    buf.write(f"{name},描述\n")
    client.post("/api/import-tasks/upload", json={"csv": buf.getvalue()})
    return client.get("/api/import-tasks").json()["tasks"][0]["task_id"]


def test_http_error_response_has_code(client):
    """404 错误：detail 保持字符串（前端兼容），并带 code 字段。"""
    resp = client.get("/api/import-tasks/not_exist_task")
    assert resp.status_code == 404
    body = resp.json()
    assert isinstance(body["detail"], str)
    assert body["code"] == "HTTP_404"


def test_business_error_response_has_code(client):
    """业务错误（400）：带 code 字段。"""
    resp = client.post("/api/import-tasks/upload", json={"csv": ""})
    assert resp.status_code == 400
    body = resp.json()
    assert isinstance(body["detail"], str)
    assert body["code"] == "HTTP_400"


def test_process_idempotent_returns_409(client):
    """process 重复触发 → 409（幂等保护）。"""
    tid = _upload(client)
    first = client.post(f"/api/import-tasks/{tid}/process", json={})
    assert first.status_code == 200
    second = client.post(f"/api/import-tasks/{tid}/process", json={})
    assert second.status_code == 409
    assert "重复触发" in second.json()["detail"]


def test_validation_error_returns_422_code(client):
    """请求体校验失败 → 422 + VALIDATION_ERROR（MetricCreateRequest 缺必填 metric_id）。"""
    resp = client.post("/api/metrics", json={})
    assert resp.status_code == 422
    assert resp.json().get("code") == "VALIDATION_ERROR"


def test_request_log_header_present(client):
    """请求日志中间件：响应头带耗时标记。"""
    resp = client.get("/api/import-tasks")
    assert resp.status_code == 200
    assert "x-request-duration-ms" in {k.lower() for k in resp.headers}
