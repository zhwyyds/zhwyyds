"""批量导入任务 API 集成测试（H31 P1）。"""

import io

import pytest
from fastapi.testclient import TestClient

from data_governance.api.app import create_app


@pytest.fixture
def client(mini_project):
    app = create_app(mini_project)
    with TestClient(app) as c:
        yield c


def _csv(*pairs: tuple[str, str]) -> str:
    buf = io.StringIO()
    buf.write("metric_cn,caliber_desc\n")
    for cn, desc in pairs:
        buf.write(f"{cn},{desc}\n")
    return buf.getvalue()


def test_upload_creates_tasks(client):
    """CSV 上传 → 生成待办任务。"""
    resp = client.post("/api/import-tasks/upload", json={"csv": _csv(("指标A", "描述A"), ("指标B", "描述B"))})
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] == 1
    task = data["tasks"][0]
    assert task["status"] == "pending"
    assert task["total_rows"] == 2
    assert task["group_no"] == 1


def test_upload_empty_rejected(client):
    resp = client.post("/api/import-tasks/upload", json={"csv": ""})
    assert resp.status_code == 400


def test_list_and_detail(client):
    client.post("/api/import-tasks/upload", json={"csv": _csv(("指标A", "描述A"))})
    tasks = client.get("/api/import-tasks").json()["tasks"]
    assert len(tasks) == 1
    detail = client.get(f"/api/import-tasks/{tasks[0]['task_id']}").json()
    assert detail["task_id"] == tasks[0]["task_id"]


def test_process_dedup_and_generate(client):
    """处理任务：库内已有指标标记 dup，新指标走 AI 生成（mock 模式）。"""
    # 先建一个已有指标（用 import 接口，状态 approved 之外皆可）
    csv_text = _csv(("月度销售额", "自然月内已完成订单销售总金额"))
    client.post("/api/import-tasks/upload", json={"csv": csv_text})
    tasks = client.get("/api/import-tasks").json()["tasks"]
    tid = tasks[0]["task_id"]

    resp = client.post(f"/api/import-tasks/{tid}/process")
    assert resp.status_code == 200
    task = resp.json()
    assert task["status"] == "reviewing"
    # 库内已有"月度销售额" → dup，应跳过（_status=skip）
    row = task["generated"][0]
    assert row["_dedup"] == "dup"
    assert row["_status"] == "skip"


def test_process_parallel_keeps_order(client):
    """并发 AI 生成（ThreadPoolExecutor + pool.map）保持卡片顺序与上传一致。"""
    rows = [(f"并发指标{i}", f"并发指标{i}的测试定义") for i in range(6)]
    client.post("/api/import-tasks/upload", json={"csv": _csv(*rows)})
    tid = client.get("/api/import-tasks").json()["tasks"][0]["task_id"]

    resp = client.post(f"/api/import-tasks/{tid}/process")
    assert resp.status_code == 200
    task = resp.json()
    pending = [g for g in task["generated"] if g["_status"] == "pending"]
    # mock 模式：全新指标全部 new → 顺序与上传一致（pool.map 保序）
    assert [g["metric_cn"] for g in pending] == [cn for cn, _ in rows]


def test_review_approve_writes_draft(client):
    """评审通过 → 指标以 draft 状态写入库。"""
    csv_text = _csv(("全新导入指标", "全新定义描述"))
    client.post("/api/import-tasks/upload", json={"csv": csv_text})
    tid = client.get("/api/import-tasks").json()["tasks"][0]["task_id"]
    client.post(f"/api/import-tasks/{tid}/process")
    task = client.get(f"/api/import-tasks/{tid}").json()
    # 找到 new 状态的行
    idx = next(i for i, r in enumerate(task["generated"]) if r["_status"] == "pending")

    resp = client.post(f"/api/import-tasks/{tid}/review", json={"row_index": idx, "action": "approve"})
    assert resp.status_code == 200
    task = resp.json()
    assert task["review_progress"]["approved"] == 1
    # 指标已入库且为 draft
    metrics = client.get("/api/metrics").json()
    assert any(m["metric_cn"] == "全新导入指标" and m["review_status"] == "draft" for m in metrics)


def test_review_reject_marks_rejected(client):
    csv_text = _csv(("另一个新指标", "定义"))
    client.post("/api/import-tasks/upload", json={"csv": csv_text})
    tid = client.get("/api/import-tasks").json()["tasks"][0]["task_id"]
    client.post(f"/api/import-tasks/{tid}/process")
    task = client.get(f"/api/import-tasks/{tid}").json()
    idx = next(i for i, r in enumerate(task["generated"]) if r["_status"] == "pending")

    resp = client.post(
        f"/api/import-tasks/{tid}/review", json={"row_index": idx, "action": "reject", "reason": "定义不清"}
    )
    assert resp.status_code == 200
    task = resp.json()
    assert task["generated"][idx]["_status"] == "rejected"
    assert task["generated"][idx]["_reject_reason"] == "定义不清"
    # 打回不入库
    metrics = client.get("/api/metrics").json()
    assert not any(m["metric_cn"] == "另一个新指标" for m in metrics)


def test_path_traversal_rejected(client):
    """恶意 task_id（路径遍历）应返回 400 而非逃逸。"""
    resp = client.get("/api/import-tasks/..%2F..%2Fetc%2Fpasswd")
    assert resp.status_code in (400, 404)
    # 也测 process/review
    resp2 = client.post("/api/import-tasks/..%2F..%2Fetc%2Fpasswd/process", json={})
    assert resp2.status_code in (400, 404)


def test_task_path_rejects_unsafe(monkeypatch, mini_project):
    """task_path 对含路径分隔符的 task_id 抛 ValueError。"""
    import pytest

    from data_governance.io.task_store import task_path

    with pytest.raises(ValueError):
        task_path(mini_project, "../../etc/passwd")
