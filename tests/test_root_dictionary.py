"""词根字典与归并工具（G2）。"""

from pathlib import Path

from data_governance.io.catalog import load_catalog
from data_governance.roots.dictionary import (
    build_root_dictionary,
    find_root_for_term,
    split_synonyms,
)


def test_split_synonyms():
    assert split_synonyms("租金|租赁|出租") == ["租金", "租赁", "出租"]
    assert split_synonyms("  a | b | a ") == ["a", "b"]
    assert split_synonyms("") == []


def test_find_root_exact_cn(mini_project: Path):
    catalog = load_catalog(mini_project)
    hit = find_root_for_term(catalog.roots, "订单", domain="sale")
    assert hit is not None and hit.root_en == "order"


def test_find_root_by_synonym(mini_project: Path):
    """同义词命中：给「订单」加同义词「销售单」后，术语「销售单」应归并到 order。"""
    from data_governance.io.roots_csv import roots_csv_path, update_root_row

    path = roots_csv_path(mini_project / "roots", "sale")
    update_root_row(path, "R_SALE_001", {"synonyms": "销售单|交易单"})
    catalog = load_catalog(mini_project)
    hit = find_root_for_term(catalog.roots, "销售单", domain="sale")
    assert hit is not None and hit.root_id == "R_SALE_001"


def test_find_root_by_root_en(mini_project: Path):
    catalog = load_catalog(mini_project)
    hit = find_root_for_term(catalog.roots, "ORDER", domain="sale")
    assert hit is not None and hit.root_cn == "订单"


def test_find_root_fuzzy_contains(mini_project: Path):
    """包含匹配：术语「订单金额」命中词根「订单」。"""
    catalog = load_catalog(mini_project)
    hit = find_root_for_term(catalog.roots, "订单金额", domain="sale")
    assert hit is not None and hit.root_en == "order"


def test_find_root_no_hit(mini_project: Path):
    catalog = load_catalog(mini_project)
    assert find_root_for_term(catalog.roots, "机器人", domain="sale") is None


def test_dictionary_prompt_text(mini_project: Path):
    catalog = load_catalog(mini_project)
    entries = build_root_dictionary(catalog.roots, domain="sale")
    text = "\n".join(e.to_prompt_line() for e in entries)
    assert "订单 → order" in text
