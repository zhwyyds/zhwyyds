"""词根字典与语义归并工具（G2）。

解决同义词词根膨胀问题：AI 生成指标/词根时，通过本模块把「已有词根库（含同义词）」
注入 prompt 并做确定性归并检查——语义已被现有词根（含同义词）覆盖的术语强制复用，
不新建词根。
"""

from __future__ import annotations

from dataclasses import dataclass

from data_governance.io.catalog import RootRecord

_SYNONYM_SEP = "|"


def split_synonyms(synonyms: str) -> list[str]:
    """把同义词字符串按 | 分隔为列表（去空、去重、保序）。"""
    if not synonyms:
        return []
    seen: list[str] = []
    for item in str(synonyms).split(_SYNONYM_SEP):
        text = item.strip()
        if text and text not in seen:
            seen.append(text)
    return seen


@dataclass
class RootDictionaryEntry:
    root: RootRecord
    synonyms: list[str]

    def to_prompt_line(self) -> str:
        extra = f"，同义词：{'、'.join(self.synonyms)}" if self.synonyms else ""
        return (
            f"- {self.root.root_cn} → {self.root.root_en}（缩写 {self.root.root_abbr}，"
            f"类型 {self.root.root_type}）{extra}"
        )


def build_root_dictionary(roots: list[RootRecord], domain: str | None = None) -> list[RootDictionaryEntry]:
    """构建词根字典（可限定域），供 prompt 注入与归并检查。"""
    entries: list[RootDictionaryEntry] = []
    for root in roots:
        if domain and root.domain_code != domain:
            continue
        entries.append(RootDictionaryEntry(root=root, synonyms=split_synonyms(root.synonyms)))
    entries.sort(key=lambda e: (e.root.domain_code, e.root.root_en))
    return entries


def dictionary_to_prompt_text(entries: list[RootDictionaryEntry]) -> str:
    if not entries:
        return "（当前词根库为空）"
    return "\n".join(e.to_prompt_line() for e in entries)


def _normalize(text: str) -> str:
    return str(text or "").strip().lower()


def find_root_for_term(
    roots: list[RootRecord],
    term: str,
    domain: str | None = None,
    *,
    fuzzy: bool = True,
) -> RootRecord | None:
    """确定性归并检查：term 是否命中已有词根（root_cn 精确/包含、同义词精确、root_en 精确）。

    - 精确匹配：root_cn == term 或 同义词 == term 或 root_en == term
    - 包含匹配（fuzzy=True）：term 包含 root_cn / root_cn 包含 term（如「租赁收入」命中「租赁」）
    """
    t = _normalize(term)
    if not t:
        return None
    candidates = [r for r in roots if (not domain or r.domain_code == domain)]
    for root in candidates:
        if _normalize(root.root_cn) == t or _normalize(root.root_en) == t:
            return root
        if t in split_synonyms(root.synonyms):
            return root
    if fuzzy:
        for root in candidates:
            rc = _normalize(root.root_cn)
            if rc and (t in rc or rc in t):
                return root
    return None
