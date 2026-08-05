"""指标级评分引擎 — 实现六维度逐检查项打分（指标级质量评分体系.md）。

设计要点：
- 每个维度拆成细粒度检查项，每项输出 score / max / status / reason（扣分原因）
- 特殊规则（同名异义→封顶C、口径空→封顶C、拼音残留→封顶B）在汇总后应用
- 模型评审维度直接消费「多模型评审明细」，把每个模型的评分与结论展示出来
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from data_governance.io.catalog import MetricRecord, ProjectCatalog, RootRecord
from data_governance.scoring.models import (
    ScoreDimension,
    ScoreIssue,
    ScoreItem,
    ScoreResult,
)
from data_governance.scoring.rules import ScoringRuleSet, load_scoring_rules

_EN_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_EN_MULTI_RE = re.compile(r"^[a-z]+(_[a-z]+)+$")
_PERIOD_KW = ("月", "周", "日", "季", "年", "自然月", "natural month", "month", "week", "quarter", "day", "daily")


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def looks_like_pinyin(token: str, root_en_set: set[str]) -> bool:
    """拼音检测：基于音节词典全切分（见 scoring/pinyin.py）。

    已注册 root_en 一律排除（避免误伤英文词根）。
    """
    from data_governance.scoring.pinyin import is_pinyin_token

    return is_pinyin_token(token, root_en_set)


def _split_root_ids(raw: str) -> list[str]:
    return [p.strip() for p in re.split(r"[;,]", raw or "") if p.strip()]


def _caliber_period_present(caliber_desc: str, frequency: str) -> bool:
    text = f"{caliber_desc} {frequency}".lower()
    return any(kw in text for kw in _PERIOD_KW)


def score_metric(
    metric: MetricRecord,
    catalog: ProjectCatalog,
    base_dir: Path,
    *,
    rules: ScoringRuleSet | None = None,
    model_review_detail: dict | None = None,
) -> ScoreResult:
    """对单个指标评分，返回完整 ScoreResult。"""
    rules = rules or load_scoring_rules()
    root_en_set = {r.root_en for r in catalog.roots if r.root_en.strip()}
    root_abbr_set = {r.root_abbr for r in catalog.roots if r.root_abbr.strip()}
    root_by_id = {r.root_id: r for r in catalog.roots}

    dimensions: list[ScoreDimension] = []
    special_hits: list[str] = []

    # ── 维度一：命名规范 ──
    naming_items, naming_veto = _score_naming(metric, root_en_set, root_abbr_set)
    if naming_veto:
        special_hits.append("拼音残留")
    dimensions.append(_dim_from_items(rules, "naming", naming_items))

    # ── 维度二：词根关联 ──
    root_items = _score_root_link(metric, root_by_id)
    dimensions.append(_dim_from_items(rules, "root_link", root_items))

    # ── 维度三：口径完整 ──
    caliber_items, caliber_veto = _score_caliber(metric)
    if caliber_veto:
        special_hits.append("口径为空")
    dimensions.append(_dim_from_items(rules, "caliber", caliber_items))

    # ── 维度四：同名同义 ──
    same_items, same_veto = _score_same_name(metric, catalog)
    if same_veto:
        special_hits.append("同名异义")
    dimensions.append(_dim_from_items(rules, "same_name", same_items))

    # ── 维度五：血缘可查 ──
    lineage_items = _score_lineage(metric, base_dir)
    dimensions.append(_dim_from_items(rules, "lineage", lineage_items))

    # ── 维度六：模型评审 ──
    review_items, review_detail, model_reviews = _score_model_review(model_review_detail)
    dim = _dim_from_items(rules, "model_review", review_items)
    dim.detail = review_detail
    dimensions.append(dim)

    total = round(sum(d.score for d in dimensions), 2)
    grade = rules.grade_for(total)

    # 应用特殊规则（封顶等级，不改变明细总分）
    capped = _apply_special_rules(grade, special_hits)
    if capped != grade:
        special_hits_effective = [s for s in special_hits if s in ("同名异义", "口径为空", "拼音残留")]
        special_hits = special_hits_effective
    grade = capped

    issues = _build_issues(dimensions, rules)
    model_reviews_out = model_reviews or (model_review_detail or {}).get("item", {}).get("model_reviews", [])

    return ScoreResult(
        metric_id=metric.metric_id,
        metric_cn=metric.metric_cn,
        metric_en=metric.metric_en,
        total_score=total,
        grade=grade,
        scored_at=_now_iso(),
        scored_by=rules.scored_by,
        dimensions=dimensions,
        special_rules=special_hits,
        issues=issues,
        model_reviews=model_reviews_out,
    )


# ── 维度打分实现 ──────────────────────────────────────────────────────────


def _score_naming(
    metric: MetricRecord, root_en_set: set[str], root_abbr_set: set[str]
) -> tuple[list[ScoreItem], bool]:
    en = metric.metric_en.strip()
    abbr = metric.metric_abbr.strip()
    items: list[ScoreItem] = []
    veto = False

    # 英文名标准化
    if not en:
        items.append(ScoreItem("英文名标准化", 0, 8, "fail", "metric_en 为空"))
    elif _EN_MULTI_RE.match(en):
        items.append(ScoreItem("英文名标准化", 8, 8, "pass", f"{en} 符合 prefix_root 格式"))
    else:
        items.append(ScoreItem("英文名标准化", 0, 8, "fail", f"{en} 不符合英文 snake_case 多段格式"))

    # 缩写可拆解
    if not abbr:
        items.append(ScoreItem("缩写可拆解", 0, 6, "fail", "metric_abbr 为空"))
    else:
        tokens = [t for t in abbr.split("_") if t]
        matched = sum(1 for t in tokens if t in root_abbr_set)
        ratio = matched / len(tokens) if tokens else 0.0
        if ratio == 1.0:
            items.append(ScoreItem("缩写可拆解", 6, 6, "pass", f"{abbr} 全部匹配 root_abbr"))
        elif ratio >= 0.5:
            items.append(ScoreItem("缩写可拆解", 3, 6, "warn", f"部分可拆解 {matched}/{len(tokens)}"))
        else:
            items.append(ScoreItem("缩写可拆解", 0, 6, "fail", f"无法拆解 {matched}/{len(tokens)} 匹配"))

    # 无拼音残留
    pinyin_tokens: list[str] = []
    for t in (en.split("_") if en else []) + (abbr.split("_") if abbr else []):
        if t and looks_like_pinyin(t, root_en_set):
            pinyin_tokens.append(t)
    if pinyin_tokens:
        veto = True
        items.append(
            ScoreItem("无拼音残留", 0, 4, "fail", f"检测到拼音片段: {', '.join(pinyin_tokens)}（启发式检测）", )
        )
    else:
        items.append(ScoreItem("无拼音残留", 4, 4, "pass", "未检测到拼音残留"))

    # 命名格式一致
    if en and _EN_MULTI_RE.match(en):
        items.append(ScoreItem("命名格式一致", 2, 2, "pass", "符合 ^[a-z]+(_[a-z]+)+$"))
    else:
        items.append(ScoreItem("命名格式一致", 0, 2, "fail", "命名格式不一致（驼峰/含大写/单段）"))

    return items, veto


def _score_root_link(metric: MetricRecord, root_by_id: dict[str, RootRecord]) -> list[ScoreItem]:
    ids = _split_root_ids(metric.root_ids)
    items: list[ScoreItem] = []

    if not ids:
        items.append(ScoreItem("词根非空", 0, 5, "fail", "root_ids 为空"))
    else:
        items.append(ScoreItem("词根非空", 5, 5, "pass", f"关联 {len(ids)} 个词根"))

    missing = [i for i in ids if i not in root_by_id]
    if ids and not missing:
        items.append(ScoreItem("词根存在", 5, 5, "pass", "所有 root_id 均存在"))
    else:
        items.append(ScoreItem("词根存在", 0, 5, "fail", f"缺失: {', '.join(missing)}" if missing else "无关联词根"))

    # 词根可逆推：metric_en 含每个关联 root_en 作为 token
    en = metric.metric_en.strip()
    if not ids:
        items.append(ScoreItem("词根可逆推", 0, 5, "fail", "无关联词根"))
    else:
        en_tokens = set(en.split("_")) if en else set()
        reversible = all((r.root_en.strip() in en_tokens) for r in (root_by_id[i] for i in ids if i in root_by_id) if r.root_en.strip())
        if reversible:
            items.append(ScoreItem("词根可逆推", 5, 5, "pass", "metric_en 可由 root_en 组合还原"))
        else:
            items.append(ScoreItem("词根可逆推", 0, 5, "fail", "metric_en 无法由关联 root_en 还原"))

    return items


def _score_caliber(metric: MetricRecord) -> tuple[list[ScoreItem], bool]:
    caliber = metric.caliber_desc.strip()
    formula = (metric.formula or "").strip() or (metric.tech_caliber or "").strip()
    freq = metric.frequency.strip()
    items: list[ScoreItem] = []
    veto = False

    if not caliber:
        veto = True
        items.append(ScoreItem("口径非空", 0, 5, "fail", "caliber_desc 为空"))
    else:
        items.append(ScoreItem("口径非空", 5, 5, "pass", "口径已填写"))

    cn_count = sum(1 for c in caliber if "一" <= c <= "鿿")
    if cn_count >= 2:
        items.append(ScoreItem("业务定义", 8, 8, "pass", "口径含业务描述"))
    elif caliber:
        items.append(ScoreItem("业务定义", 4, 8, "warn", "业务定义偏简，建议补充业务含义"))
    else:
        items.append(ScoreItem("业务定义", 0, 8, "fail", "无业务定义"))

    if formula:
        items.append(ScoreItem("计算公式", 7, 7, "pass", "已提供计算公式"))
    else:
        items.append(ScoreItem("计算公式", 0, 7, "fail", "缺少计算公式"))

    if _caliber_period_present(caliber, freq):
        items.append(ScoreItem("统计周期", 5, 5, "pass", "口径或频率明确统计周期"))
    else:
        items.append(ScoreItem("统计周期", 0, 5, "fail", "未明确统计周期"))

    return items, veto


def _score_same_name(metric: MetricRecord, catalog: ProjectCatalog) -> tuple[list[ScoreItem], bool]:
    metrics = catalog.metrics
    en = metric.metric_en.strip()
    caliber = metric.caliber_desc.strip()
    items: list[ScoreItem] = []
    veto = False

    # 同名异义
    homonym = [
        m for m in metrics
        if m.metric_en.strip() == en and m.caliber_desc.strip() and m.caliber_desc.strip() != caliber and m.metric_id != metric.metric_id
    ]
    if homonym:
        veto = True
        items.append(
            ScoreItem("无同名异义", 0, 10, "fail", f"同名异义 {len(homonym)} 例: {', '.join(m.metric_id for m in homonym[:3])}")
        )
    else:
        items.append(ScoreItem("无同名异义", 10, 10, "pass", "全库无同名异义"))

    # 同义异名（精确 caliber 匹配）
    synonym = [
        m for m in metrics
        if m.caliber_desc.strip() == caliber and caliber and m.metric_en.strip() != en and m.metric_id != metric.metric_id
    ]
    if synonym:
        deduct = min(7.0, 3.0 * len(synonym))
        items.append(
            ScoreItem("无同义异名", round(7 - deduct, 1), 7, "warn", f"同义异名 {len(synonym)} 例（精确口径匹配）")
        )
    else:
        items.append(ScoreItem("无同义异名", 7, 7, "pass", "无同义异名"))

    # 名称口径一致
    cn = metric.metric_cn.strip()
    if cn and any(c in caliber for c in cn if "一" <= c <= "鿿"):
        items.append(ScoreItem("名称口径一致", 3, 3, "pass", "中文名与口径语义一致"))
    elif cn:
        items.append(ScoreItem("名称口径一致", 0, 3, "fail", "中文名与口径未见明显语义关联"))
    else:
        items.append(ScoreItem("名称口径一致", 0, 3, "fail", "metric_cn 为空"))

    return items, veto


def _score_lineage(metric: MetricRecord, base_dir: Path) -> list[ScoreItem]:
    domain = metric.domain_code.strip()
    items: list[ScoreItem] = []

    lineage_id = (metric.tree_node_id or "").strip() or (metric.source_table or "").strip()
    if lineage_id:
        items.append(ScoreItem("血缘ID非空", 3, 3, "pass", f"lineage ref: {lineage_id}"))
    else:
        items.append(ScoreItem("血缘ID非空", 0, 3, "fail", "tree_node_id / source_table 均为空"))

    path = base_dir / "lineage" / f"{domain}_lineage.json"
    entry = None
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        for e in data.get("lineages") or []:
            related = e.get("related_metrics") or []
            if metric.metric_id in related or (metric.source_table and e.get("target_table") == metric.source_table):
                entry = e
                break

    if entry is not None:
        items.append(ScoreItem("血缘记录存在", 4, 4, "pass", "血缘记录命中"))
    else:
        items.append(ScoreItem("血缘记录存在", 0, 4, "fail", "血缘记录未命中该指标"))

    if entry and entry.get("column_mappings"):
        items.append(ScoreItem("字段级映射", 3, 3, "pass", f"含 {len(entry['column_mappings'])} 个字段映射"))
    else:
        items.append(ScoreItem("字段级映射", 0, 3, "fail", "无字段级映射"))

    return items


def _score_model_review(model_review_detail: dict | None) -> tuple[list[ScoreItem], str, list[dict]]:
    items: list[ScoreItem] = []
    if not model_review_detail or "item" not in model_review_detail:
        items.append(ScoreItem("经过模型评审", 0, 5, "fail", "无模型评审记录"))
        items.append(ScoreItem("评审记录完整", 0, 3, "fail", "无评审记录"))
        items.append(ScoreItem("评审通过", 0, 2, "fail", "未通过模型评审"))
        return items, "未经多模型评审（source=manual）", []

    item = model_review_detail["item"]
    model_reviews: list[dict] = item.get("model_reviews", []) or []
    comparison = item.get("comparison") or {}
    final = item.get("final_decision") or {}

    items.append(
        ScoreItem("经过模型评审", 5 if len(model_reviews) >= 2 else 0, 5, "pass" if len(model_reviews) >= 2 else "fail",
                  f"参与模型 {len(model_reviews)} 个" if len(model_reviews) >= 2 else f"仅 {len(model_reviews)} 个模型，不足 2")
    )
    complete = bool(model_reviews) and bool(comparison) and bool(final)
    items.append(
        ScoreItem("评审记录完整", 3 if complete else 0, 3, "pass" if complete else "fail",
                  "model_reviews+comparison+final_decision 齐全" if complete else "评审 JSON 结构不完整")
    )
    approved = bool(final.get("approved"))
    items.append(
        ScoreItem("评审通过", 2 if approved else 0, 2, "pass" if approved else "fail",
                  f"决策: {final.get('decision_type', 'unknown')}")
    )

    # 多模型明细（用于 UI 展示）
    lines: list[str] = []
    for mr in model_reviews:
        lines.append(
            f"{mr.get('model')}: 命名 {mr.get('naming_score')}/5, 口径 {mr.get('caliber_score')}/5, "
            f"词根匹配 {'是' if mr.get('root_match') else '否'}"
            + (f", 建议: {mr.get('suggestions')}" if mr.get("suggestions") else "")
        )
    if comparison:
        lines.append(
            f"汇总: 命名均分 {comparison.get('naming_score_avg')}, 口径均分 {comparison.get('caliber_score_avg')}"
            + (", 存在冲突" if comparison.get("conflict_detected") else ", 无冲突")
        )
    detail = "\n".join(lines) if lines else "无模型评审明细"
    return items, detail, model_reviews


# ── 聚合与封顶 ────────────────────────────────────────────────────────────


def _dim_from_items(rules: ScoringRuleSet, dim_code: str, items: list[ScoreItem]) -> ScoreDimension:
    rule = next((d for d in rules.dimensions if d.dim_code == dim_code), None)
    max_score = rule.max_score if rule else sum(i.max_score for i in items)
    score = round(sum(i.score for i in items), 2)
    if score >= max_score:
        status = "pass"
    elif score <= 0:
        status = "fail"
    else:
        status = "warn"
    name = rule.dim_name if rule else dim_code
    return ScoreDimension(dim_code=dim_code, dim_name=name, score=score, max_score=max_score, status=status, items=items)


_GRADE_ORDER = ["D", "C", "B", "A", "S"]


def _apply_special_rules(grade: str, hits: list[str]) -> str:
    """根据特殊规则封顶等级。"""
    cap = None
    if "同名异义" in hits or "口径为空" in hits:
        cap = "C"
    elif "拼音残留" in hits:
        cap = "B"
    if cap is None:
        return grade
    if _GRADE_ORDER.index(grade) > _GRADE_ORDER.index(cap):
        return cap
    return grade


def _build_issues(dimensions: list[ScoreDimension], rules: ScoringRuleSet) -> list[ScoreIssue]:
    issues: list[ScoreIssue] = []
    for dim in dimensions:
        for it in dim.items:
            if it.status == "pass":
                continue
            priority = "P1" if it.status == "fail" else "P2"
            suggestion = _suggest_for(it.item, dim.dim_code)
            issues.append(
                ScoreIssue(
                    priority=priority,
                    dimension=dim.dim_code,
                    issue=f"[{dim.dim_name}] {it.item}：{it.reason or '不达标'}",
                    suggestion=suggestion,
                    fix_action=_fix_action_for(it.item, dim.dim_code),
                )
            )
    return issues


def _suggest_for(item: str, dim_code: str) -> str:
    mapping = {
        "英文名标准化": "按 root_en 组合重写 metric_en（snake_case 多段）",
        "缩写可拆解": "metric_abbr 改为已注册 root_abbr 的组合",
        "无拼音残留": "将拼音命名替换为英文词根组合",
        "命名格式一致": "统一为小写下划线命名",
        "词根非空": "补充关联词根 root_ids",
        "词根存在": "先注册缺失的词根或修正 root_id",
        "词根可逆推": "使 metric_en 可由关联 root_en 组合还原",
        "口径非空": "填写 caliber_desc",
        "业务定义": "补充业务含义描述",
        "计算公式": "补充 formula / tech_caliber",
        "统计周期": "在口径或 frequency 中明确统计周期",
        "无同名异义": "与同名指标对齐口径或重命名",
        "无同义异名": "合并同义指标或差异化命名",
        "名称口径一致": "对齐中文名与口径语义",
        "血缘ID非空": "填写 tree_node_id / source_table",
        "血缘记录存在": "补充 lineage JSON 记录",
        "字段级映射": "补充 column_mappings",
        "经过模型评审": "提交多模型评审流程",
        "评审记录完整": "确保评审含多模型+比对+结论",
        "评审通过": "根据评审意见整改后重新评审",
    }
    return mapping.get(item, "按规则整改")


def _fix_action_for(item: str, dim_code: str) -> str:
    if dim_code == "model_review":
        return "点击「提交评审」"
    if dim_code == "lineage":
        return "编辑血缘"
    return "修改指标字段"
