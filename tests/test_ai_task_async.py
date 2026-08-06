"""验证异步 AI 任务（I1 多 AI 进度）：2 模型并行，completed 递增 0→1→2→done。"""

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


class _SlowClient:
    """带延迟的 fake LLM（模拟多模型并行，逐个完成）。"""

    model_name = "fake"

    def __init__(self, name: str, delay: float) -> None:
        self.model_name = name
        self.delay = delay

    def complete(self, prompt: str) -> str:
        time.sleep(self.delay)
        return (
            '{"metric_en":"monthly_rent_amount",'
            '"caliber_desc":"自然月应收租金","unit":"元","frequency":"月",'
            '"suggested_roots":[]}'
        )


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch, mini_project: Path) -> TestClient:
    from data_governance.api.app import create_app
    from data_governance.llm import factory as llm_factory

    clients = [_SlowClient("deepseek-a", 0.4), _SlowClient("deepseek-b", 0.8)]
    monkeypatch.setattr(llm_factory, "build_live_clients", lambda configs: clients)
    monkeypatch.setenv("DATA_GOV_LLM_MODE", "live")
    return TestClient(create_app(mini_project))


def test_async_suggest_progress_increments(api_client: TestClient):
    """2 模型并行：任务进度 completed 从 0 递增到 2，最终 done 且有结果。"""
    r = api_client.post("/api/metrics/suggest/async", json={"metric_cn": "月度租赁收入", "domain_code": "sale"})
    assert r.status_code == 200, r.text
    task_id = r.json()["task_id"]

    # 轮询进度：应观察到 completed=0 → 1 → 2 → status=done
    seen = set()
    final = None
    for _ in range(30):  # 最多 3s
        st = api_client.get(f"/api/ai-tasks/{task_id}").json()
        seen.add(st["completed"])
        if st["status"] == "done":
            final = st
            break
        time.sleep(0.1)

    assert final is not None, f"任务未完成，观察到的进度: {seen}"
    assert final["status"] == "done"
    assert final["total"] == 2, f"应报告 2 个模型，实际 {final['total']}"
    assert 1 in seen, f"应观察到中间进度 completed=1，实际 {seen}"
    assert final["result"]["metric_en"] == "monthly_rent_amount"


def test_async_task_not_found(api_client: TestClient):
    """不存在的 task_id → 404。"""
    r = api_client.get("/api/ai-tasks/no_such_task")
    assert r.status_code == 404
