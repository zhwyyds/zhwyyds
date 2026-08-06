"""批量导入任务存储与去重（H31 P1）测试。"""

from data_governance.io.catalog import load_catalog
from data_governance.io.task_store import (
    create_import_tasks,
    dedup_rows,
    get_import_task,
    list_import_tasks,
    split_csv,
    update_import_task,
)


def test_split_csv_groups_by_50(tmp_path, mini_project):
    """CSV 按 50 条/组切分，空行跳过。"""
    rows = ["metric_cn,caliber_desc"]
    rows += [f"指标{i},描述{i}" for i in range(120)]
    groups = split_csv("\n".join(rows))
    assert len(groups) == 3
    assert len(groups[0]) == 50
    assert len(groups[1]) == 50
    assert len(groups[2]) == 20


def test_split_csv_skips_empty_cn(tmp_path, mini_project):
    rows = ["metric_cn,caliber_desc", "有效指标,描述", ",无名称", "另一个,描述"]
    groups = split_csv("\n".join(rows))
    assert len(groups[0]) == 2


def test_create_and_list_tasks(tmp_path, mini_project):
    """创建任务落盘，列表可读，字段完整。"""
    rows = ["metric_cn,caliber_desc"] + [f"新指标{i},描述{i}" for i in range(60)]
    tasks = create_import_tasks(mini_project, "\n".join(rows))
    assert len(tasks) == 2  # 60 条 → 2 组
    t = tasks[0]
    assert t["status"] == "pending"
    assert t["total_rows"] == 50
    assert t["group_no"] == 1
    # 落盘可读
    loaded = get_import_task(mini_project, t["task_id"])
    assert loaded is not None
    assert loaded["task_id"] == t["task_id"]
    # 列表
    listed = list_import_tasks(mini_project)
    assert len(listed) == 2


def test_update_task_status(tmp_path, mini_project):
    rows = ["metric_cn,caliber_desc", "指标A,描述A"]
    tasks = create_import_tasks(mini_project, "\n".join(rows))
    updated = update_import_task(mini_project, tasks[0]["task_id"], status="processing")
    assert updated["status"] == "processing"


def test_dedup_exact_and_suspect(mini_project):
    """去重：精确命中 dup、归一化命中 suspect、新条目 new。"""
    catalog = load_catalog(mini_project)
    # mini_project 里有"月度销售额"（sale_metrics.csv 第 1 条）
    rows = [
        {"metric_cn": "月度销售额", "caliber_desc": "重复"},
        {"metric_cn": "月度销售额指标", "caliber_desc": "疑似（归一化后命中）"},
        {"metric_cn": "全新指标X", "caliber_desc": "新增"},
    ]
    result = dedup_rows(rows, catalog)
    assert result["dup_count"] == 1
    assert result["suspect_count"] == 1
    assert result["new_count"] == 1
    assert result["new_rows"][0]["metric_cn"] == "全新指标X"


def test_dedup_all_new(mini_project):
    catalog = load_catalog(mini_project)
    rows = [{"metric_cn": f"全新{i}", "caliber_desc": "d"} for i in range(5)]
    result = dedup_rows(rows, catalog)
    assert result["new_count"] == 5
    assert result["dup_count"] == 0
