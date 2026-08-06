"""口径助手 — 多模型起草 + 共识汇总（IT2-4，口径字段标准与迁移方案.md）。

工作流：
  含糊定义 → 多模型各自产出结构化口径 JSON → 共识比对（逐字段多数/最优）
  → 推荐版 + diff_summary + high_risk → 落库 caliber_* 字段 + status=pending
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from data_governance.io.catalog import MetricRecord

# 口径结构化字段（与 METRIC_CSV_FIELDS / MetricRecord 对齐）
CALIBER_FIELDS = (
    "caliber_business",
    "caliber_formula",
    "caliber_period",
    "caliber_granularity",
    "caliber_boundary",
    "caliber_source",
)

_JSON_BLOCK_RE = re.compile(r"\{[^{}]*\}")


@dataclass
class CaliberDraftResult:
    metric_id: str
    draft: dict  # 推荐版
    by_model: dict[str, dict] = field(default_factory=dict)
    diff_summary: list[dict] = field(default_factory=list)
    high_risk: bool = False
    ai_by: str = ""


def build_prompt(metric: MetricRecord) -> str:
    """构造口径起草 prompt：输入含糊定义，要求输出结构化 JSON。"""
    return f"""你是数据治理平台的指标口径专家。请根据下面这个「含糊的指标定义」，输出一份精准、结构化的口径定义。

指标中文名：{metric.metric_cn}
指标英文名：{metric.metric_en or "（无）"}
现有口径描述：{metric.caliber_desc or "（无）"}
统计频率：{metric.frequency or "（未定）"}
来源表：{metric.source_table or metric.data_sources or "（未定）"}

要求：
1. 只输出一个 JSON 对象，不要多余文字
2. 字段：
   - caliber_business: 一句话说清「这个指标是什么」（含统计范围、是否含退款等边界）
   - caliber_formula: 计算公式（SQL 表达式风格）
   - caliber_period: 统计周期（月/周/日/季/年/累计）
   - caliber_granularity: 计算粒度（如：订单行级/用户级）
   - caliber_boundary: 边界与排除条件（不含哪些、按什么时间归属）
   - caliber_source: 建议的来源表/字段
   - suggestions: 你认为还需人工确认的点（数组）
3. 若现有定义含糊，请补全，不要简单照抄
"""


def _find_balanced(text: str, opener: str) -> str | None:
    """在 text 中找到第一个 balanced {…} 或 […]（支持嵌套与字符串内括号）。"""
    idx = text.find(opener)
    if idx < 0:
        return None
    closer = "}" if opener == "{" else "]"
    depth = 1
    in_str = False
    esc = False
    for j in range(idx + 1, len(text)):
        ch = text[j]
        if esc:
            esc = False
            continue
        if ch == "\\" and in_str:
            esc = True
            continue
        if ch == '"' and not esc:
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[idx : j + 1]
    return None


def parse_response(text: str) -> dict:
    """容错解析 LLM 返回的 JSON 字典：支持 markdown 包裹 / 嵌套 / list-wrapped。

    返回 dict；解析失败返回空字典（调用方按需处理）。
    """
    text = (text or "").strip()
    if not text:
        return {}
    # 1. 剥 markdown ```json\n{…}\n``` 包裹
    md = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if md:
        text = md.group(1).strip()
    # 2. 找第一个 balanced {...} 或 [...]（支持任意嵌套）
    candidates = []
    for opener in ("{", "["):
        sub = _find_balanced(text, opener)
        if sub:
            candidates.append(sub)
    if not candidates:
        candidates.append(text)
    # 3. 按顺序尝试解析，dict 优先；list-wrap 取首个 dict
    for sub in candidates:
        try:
            obj = json.loads(sub)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
        if isinstance(obj, list) and obj and isinstance(obj[0], dict):
            return obj[0]
    return {}


def _mock_draft(metric: MetricRecord, model_name: str) -> dict:
    """确定性 mock 草稿（不同模型措辞略有差异，供共识比对演示）。"""
    cn = metric.metric_cn
    desc = metric.caliber_desc or cn
    period = metric.frequency or "月"
    source = metric.source_table or metric.data_sources or "（待补充来源表）"
    base = {
        "caliber_business": f"{cn}：{desc}（不含退款，按自然{period}归属）",
        "caliber_formula": f"SUM({cn}对应金额字段) WHERE 统计周期=当前自然{period}",
        "caliber_period": period,
        "caliber_granularity": "按业务明细行",
        "caliber_boundary": "不含退款；按支付完成时间归属统计周期",
        "caliber_source": source,
        "suggestions": ["建议人工确认是否含税", "建议确认统计时区"],
    }
    if "claude" in model_name:
        base["caliber_boundary"] = "不含退款；按支付完成时间归属；跨天交易按交易完成日归属"
        base["suggestions"] = ["建议人工确认是否含税", "建议确认统计时区", "建议确认跨境订单归属"]
    if "qwen" in model_name:
        base["caliber_granularity"] = "订单行级（单笔订单多行时按行汇总）"
        base["suggestions"] = ["建议人工确认是否含税", "建议确认统计时区", "建议确认折扣后金额口径"]
    return base


def merge_drafts(drafts: list[tuple[str, dict]]) -> tuple[dict, list[dict], bool]:
    """逐字段多数投票取推荐；记录分歧；business 分歧或 ≥2 字段分歧标记 high_risk。"""
    merged: dict[str, str] = {}
    diff_summary: list[dict] = []
    for field_name in CALIBER_FIELDS:
        values = {name: (d.get(field_name) or "").strip() for name, d in drafts}
        counter = Counter(v for v in values.values() if v)
        if not counter:
            merged[field_name] = ""
            continue
        top_value, _ = counter.most_common(1)[0]
        merged[field_name] = top_value
        divergent = [n for n, v in values.items() if v and v != top_value]
        if divergent:
            diff_summary.append(
                {
                    "field": field_name,
                    "models": [n for n, _ in drafts],
                    "consensus": top_value,
                    "divergent": divergent,
                }
            )
    high_risk = any(d["field"] == "caliber_business" for d in diff_summary) or len(diff_summary) >= 2
    return merged, diff_summary, high_risk


def draft_caliber(
    metric: MetricRecord,
    *,
    base_dir: Path,
    use_mock: bool | None = None,
) -> CaliberDraftResult:
    """多模型起草口径：mock 确定性出稿 / live 并行调用，输出推荐版 + 差异说明。"""
    from data_governance.config_loader import load_models
    from data_governance.llm.env import resolve_use_mock
    from data_governance.llm.factory import build_live_clients
    from data_governance.llm.mock import MockLLMClient
    from data_governance.llm.parallel import run_models_parallel_mock, run_models_parallel_prompt

    models = load_models("metric_review", config_path=base_dir / "config" / "models.csv")
    model_names = [m.model_name for m in models]
    use_mock = resolve_use_mock(use_mock)

    if use_mock:
        from data_governance.llm.mock import MockLLMClient

        def _make_responder() -> Any:
            def responder(mname: str, _batch: list[Any]) -> list[dict]:
                return [_mock_draft(metric, mname)]

            return responder

        clients = [MockLLMClient(name, responder=_make_responder()) for name in model_names]
        raw = run_models_parallel_mock(clients, [metric])
    else:
        live_clients = build_live_clients(models)
        prompt = build_prompt(metric)
        raw = run_models_parallel_prompt(live_clients, prompt, cache_base_dir=base_dir)

    drafts = {name: parse_response(text) for name, text in raw}
    merged, diff_summary, high_risk = merge_drafts(list(drafts.items()))
    ai_by = ";".join(drafts.keys()) + ("(consensus)" if not high_risk else "(divergent)")
    return CaliberDraftResult(
        metric_id=metric.metric_id,
        draft=merged,
        by_model=drafts,
        diff_summary=diff_summary,
        high_risk=high_risk,
        ai_by=ai_by,
    )


def persist_draft(base_dir: Path, metric_id: str, result: CaliberDraftResult) -> MetricRecord:
    """把推荐版落库：caliber_* 字段 + status=pending。"""
    from data_governance.io.metrics_csv import upsert_metric

    payload: dict[str, Any] = dict(result.draft)
    payload["caliber_status"] = "pending"
    payload["caliber_ai_by"] = result.ai_by
    return upsert_metric(base_dir, metric_id, payload)
