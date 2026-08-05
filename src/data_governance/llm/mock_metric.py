from __future__ import annotations

from data_governance.schemas.metrics import MetricInput


def default_monthly_sales_fixture() -> dict[str, dict[str, dict]]:
    """文档 §3.5 M_SALE_001 三模型评审."""
    mid = "M_SALE_001"
    return {
        "gpt-4o": {
            mid: {
                "naming_score": 5,
                "naming_issues": [],
                "caliber_score": 4,
                "caliber_issues": ["口径未明确是否含税"],
                "conflict_risks": [],
                "root_match": True,
                "suggestions": "建议口径中补充是否含税说明",
            }
        },
        "claude-3.5-sonnet": {
            mid: {
                "naming_score": 5,
                "naming_issues": [],
                "caliber_score": 4,
                "caliber_issues": ["口径未明确是否含税"],
                "conflict_risks": [],
                "root_match": True,
                "suggestions": "建议补充含税/不含税说明",
            }
        },
        "qwen-plus": {
            mid: {
                "naming_score": 4,
                "naming_issues": ["建议使用 monthly_sales_amount 更完整"],
                "caliber_score": 3,
                "caliber_issues": ["口径未明确含税、未明确统计时区"],
                "conflict_risks": [],
                "root_match": True,
                "suggestions": "建议口径补充含税说明和统计时区",
            }
        },
    }


def metric_clients_from_fixture(
    model_names: list[str],
    fixture: dict[str, dict[str, dict]],
) -> list:
    from data_governance.llm.mock import MockLLMClient

    clients: list[MockLLMClient] = []

    def make_responder(name: str) -> MockLLMClient:
        # 未配置 fixture 的模型（如后加的 DeepSeek）复用第一个模型的响应
        fallback = next(iter(fixture.values()), {})
        per_metric = fixture.get(name) or fallback

        def responder(model: str, metrics: list[MetricInput]) -> list[dict]:
            del model
            out = []
            for m in metrics:
                if m.metric_id not in per_metric:
                    raise KeyError(f"{name}: no data for {m.metric_id!r}")
                row = dict(per_metric[m.metric_id])
                row["metric_id"] = m.metric_id
                out.append(row)
            return out

        return MockLLMClient(name, responder=responder)

    for name in model_names:
        if name in fixture:  # mock 只对 fixture 定义的模型出稿（新增模型仅 live 生效）
            clients.append(make_responder(name))
    return clients
