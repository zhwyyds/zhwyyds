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

{root_dictionary_section}
术语列表：
{terms_json}

请以 JSON 数组格式输出，每个术语包含：cn_term, root_en, root_abbr, root_type, description
"""


def build_root_generation_prompt(
    terms: list[TermInput],
    *,
    root_dictionary_text: str = "",
) -> str:
    """构造词根生成 prompt。

    root_dictionary_text：既有词根字典（含同义词），用于强制复用——语义已被覆盖的
    术语必须复用已有词根（返回已有 root_en），禁止自创新词根。
    """
    if root_dictionary_text and root_dictionary_text.strip() != "（当前词根库为空）":
        section = (
            "词根强制复用规则（必须严格遵守）：\n"
            "- 术语的语义若已被下方既有词根覆盖（含其同义词），必须返回该词根的 root_en/root_abbr/root_type，"
            "并在 description 中注明「复用词根 <root_id>」\n"
            "- 禁止为已有语义创建新词根（如已有 rent（租金/租赁），不得输出 lease）\n"
            "- 仅当语义确无对应词根时才生成新词根\n"
            "既有词根库（含同义词）：\n"
            f"{root_dictionary_text.strip()}\n"
        )
    else:
        section = "（无既有词根库约束）"
    payload = [t.model_dump() for t in terms]
    terms_json = json.dumps(payload, ensure_ascii=False, indent=2)
    return ROOT_GENERATION_TEMPLATE.format(
        root_dictionary_section=section,
        terms_json=terms_json,
    )
