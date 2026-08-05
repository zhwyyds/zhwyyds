from __future__ import annotations

import json

from data_governance.schemas.roots import TermInput

ROOT_GENERATION_TEMPLATE = """你是一位数据治理专家，精通英文命名规范。请将以下中文术语翻译为标准化的英文词根。

要求：
1. 给出英文全称（root_en）：使用标准英文单词，不用拼音
2. 给出英文缩写（root_abbr）：不超过6个字符，遵循以下规则：
   - 单词取前3-4个字母（如 customer → cust）
   - 短词直接用全称（如 id, name）
   - 多词组合取首字母或缩写拼接
3. 给出词根类型（root_type）：noun/verb/adj/unit/time
4. 给出简短说明

术语列表：
{terms_json}

请以 JSON 数组格式输出，每个术语包含：cn_term, root_en, root_abbr, root_type, description
"""


def build_root_generation_prompt(terms: list[TermInput]) -> str:
    payload = [t.model_dump() for t in terms]
    terms_json = json.dumps(payload, ensure_ascii=False, indent=2)
    return ROOT_GENERATION_TEMPLATE.format(terms_json=terms_json)
