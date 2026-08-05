from __future__ import annotations

import re
from collections import Counter
from math import ceil

from data_governance.schemas.roots import (
    DecisionType,
    ModelRootResult,
    ReviewStatus,
    RootComparison,
    RootFinalDecision,
    RootType,
)

_ABBR_RE = re.compile(r"^[a-z][a-z0-9_]{0,5}$")


def abbr_norm_score(abbr: str) -> int:
    """Higher is better. M1: length + charset."""
    if not abbr:
        return 0
    score = 10
    if len(abbr) > 6:
        score -= 20
    if _ABBR_RE.match(abbr):
        score += 5
    return score


def _majority(values: list[str], n: int) -> tuple[str | None, bool, bool]:
    """Return (winning value, has_majority, all_equal)."""
    if not values:
        return None, False, True
    counts = Counter(values)
    value, count = counts.most_common(1)[0]
    need = ceil(2 / 3 * n)
    all_equal = len(counts) == 1
    has_majority = count >= need
    if has_majority:
        return value, True, all_equal
    return None, False, all_equal


def compare_field(values: list[str], n: int) -> tuple[bool, list[str]]:
    """Consistent if all equal OR clear >=2/3 majority on one value."""
    _, has_majority, all_equal = _majority(values, n)
    if all_equal:
        return True, []
    if has_majority:
        return True, []
    return False, []


def pick_field_value(field: str, results: list[ModelRootResult]) -> tuple[str | None, bool]:
    n = len(results)
    if field == "root_en":
        values = [r.root_en for r in results]
    elif field == "root_abbr":
        values = [r.root_abbr for r in results]
    elif field == "root_type":
        values = [r.root_type.value for r in results]
    else:
        raise ValueError(field)

    counts = Counter(values)
    need = ceil(2 / 3 * n)
    best_value: str | None = None
    best_count = 0
    for val, cnt in counts.most_common():
        if cnt > best_count:
            best_value, best_count = val, cnt

    if best_count >= need:
        if field == "root_abbr" and len([v for v, c in counts.items() if c == best_count]) > 1:
            candidates = [v for v, c in counts.items() if c == best_count]
            best_value = max(candidates, key=abbr_norm_score)
        return best_value, True
    if len(counts) == 1:
        return best_value, True
    return None, False


def build_comparison(results: list[ModelRootResult]) -> RootComparison:
    if not results:
        raise ValueError("empty results")
    conflicts: list[str] = []
    if len({r.root_en for r in results}) != 1:
        conflicts.append("root_en")
    if len({r.root_abbr for r in results}) != 1:
        conflicts.append("root_abbr")
    if len({r.root_type.value for r in results}) != 1:
        conflicts.append("root_type")
    return RootComparison(
        root_en_consistent=len({r.root_en for r in results}) == 1,
        root_abbr_consistent=len({r.root_abbr for r in results}) == 1,
        root_type_consistent=len({r.root_type.value for r in results}) == 1,
        conflict_fields=conflicts,
    )


def _pick_description(results: list[ModelRootResult], chosen_en: str, chosen_abbr: str) -> str:
    for r in results:
        if r.root_en == chosen_en and r.root_abbr == chosen_abbr and r.description:
            return r.description
    for r in results:
        if r.root_en == chosen_en and r.description:
            return r.description
    for r in results:
        if r.description:
            return r.description
    return ""


def decide_root(
    results: list[ModelRootResult],
    *,
    comparison: RootComparison | None = None,
) -> tuple[RootFinalDecision, bool]:
    if len(results) < 2:
        raise ValueError("need at least 2 model results")

    comp = comparison or build_comparison(results)
    en_val, en_ok = pick_field_value("root_en", results)
    ab_val, ab_ok = pick_field_value("root_abbr", results)
    ty_val, ty_ok = pick_field_value("root_type", results)

    if not (en_ok and ab_ok and ty_ok) or en_val is None or ab_val is None or ty_val is None:
        placeholder = results[0]
        return (
            RootFinalDecision(
                root_en=placeholder.root_en,
                root_abbr=placeholder.root_abbr,
                root_type=placeholder.root_type,
                description=placeholder.description,
                decision_reason="无可靠多数，需人工确认",
                decision_type=DecisionType.model_conflict,
                review_status=ReviewStatus.pending,
            ),
            False,
        )

    root_type = RootType(ty_val)
    description = _pick_description(results, en_val, ab_val)

    all_same = (
        len({r.root_en for r in results}) == 1
        and len({r.root_abbr for r in results}) == 1
        and len({r.root_type for r in results}) == 1
    )
    if all_same:
        decision_type = DecisionType.model_consensus
        reason = "所有模型结果完全一致"
        source_status = ReviewStatus.approved
    else:
        decision_type = DecisionType.model_majority
        reason = "采用多数模型一致的结果"
        if comp.conflict_fields:
            parts = []
            if "root_abbr" in comp.conflict_fields or not comp.root_abbr_consistent:
                parts.append("root_abbr 存在分歧但多数表决")
            source_status = ReviewStatus.approved
            reason = "；".join(parts) if parts else reason
        else:
            source_status = ReviewStatus.approved

    return (
        RootFinalDecision(
            root_en=en_val,
            root_abbr=ab_val,
            root_type=root_type,
            description=description,
            decision_reason=reason,
            decision_type=decision_type,
            review_status=source_status,
        ),
        True,
    )


def decision_to_source_model(decision_type: DecisionType) -> str | None:
    if decision_type == DecisionType.model_consensus:
        return "model_consensus"
    if decision_type == DecisionType.model_majority:
        return "model_majority"
    return None
