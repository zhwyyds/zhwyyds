from __future__ import annotations

import json

from data_governance.schemas.metrics import MetricInput

METRIC_REVIEW_TEMPLATE = """你是一位数据治理评审专家。请对以下指标定义进行评审，检查以下方面：

1. 命名规范性：metric_en 是否由标准词根组合而成，是否符合英文命名规范
2. 口径清晰度：caliber_desc 是否清晰、无歧义，是否包含业务定义和计算逻辑
3. 同名同义风险：该指标名称是否可能与其他指标产生同名异义或同义异名
4. 词根关联性：root_ids 关联的词根是否能正确还原为 metric_en
5. 单位与频率：unit 和 frequency 是否合理

指标列表：
{metrics_json}

请以 JSON 数组格式输出评审结果，每个指标包含：
metric_id, naming_score(1-5), naming_issues, caliber_score(1-5),
caliber_issues, conflict_risks, root_match(true/false), suggestions,
revision

字段格式要求（必须严格遵守）：
- naming_issues / caliber_issues / conflict_risks 必须是字符串数组，例如 ["问题1", "问题2"]；没有问题则为 []，绝不能写成一句话或字符串
- root_match 只能是 true 或 false（不带引号）
- naming_score / caliber_score 只能是 1-5 的整数
- suggestions 是单条字符串
- revision 是"修订建议"对象：当发现问题时，给出可直接落库的修正值，格式：
  {{"metric_cn": "修正后的中文名", "metric_en": "修正后的英文名", "caliber_desc": "补充/修正后的口径定义",
   "unit": "修正后的单位", "frequency": "修正后的统计频率", "root_ids": ["R_XX_001"], "summary": "本次修订说明（一句话）"}}
  只有需要修改的字段才给出；无需修改的字段省略或给 null；完全没有修订建议时为 null。

只输出 JSON，不要包含 markdown 代码块标记或其他解释文字。
"""


def build_metric_review_prompt(metrics: list[MetricInput]) -> str:
    payload = [m.model_dump() for m in metrics]
    metrics_json = json.dumps(payload, ensure_ascii=False, indent=2)
    return METRIC_REVIEW_TEMPLATE.format(metrics_json=metrics_json)
