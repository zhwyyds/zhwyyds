from data_governance.compare.roots import build_comparison, decide_root
from data_governance.schemas.roots import DecisionType, ModelRootResult, RootType


def _result(model: str, abbr: str) -> ModelRootResult:
    return ModelRootResult(
        model=model,
        root_en="customer",
        root_abbr=abbr,
        root_type=RootType.noun,
        description="客户的统称",
    )


def test_customer_majority_abbr():
    results = [
        _result("gpt-4o", "cust"),
        _result("claude-3.5-sonnet", "cust"),
        _result("glm-4", "cst"),
    ]
    comp = build_comparison(results)
    assert comp.root_en_consistent is True
    assert comp.root_abbr_consistent is False
    assert "root_abbr" in comp.conflict_fields or not comp.root_abbr_consistent

    final, auto = decide_root(results, comparison=comp)
    assert auto is True
    assert final.root_abbr == "cust"
    assert final.decision_type == DecisionType.model_majority


def test_full_consensus():
    results = [_result("a", "cust"), _result("b", "cust"), _result("c", "cust")]
    final, auto = decide_root(results)
    assert auto is True
    assert final.decision_type == DecisionType.model_consensus


def test_three_way_conflict():
    results = [
        ModelRootResult(
            model="a",
            root_en="customer",
            root_abbr="cust",
            root_type=RootType.noun,
            description="",
        ),
        ModelRootResult(
            model="b",
            root_en="client",
            root_abbr="cli",
            root_type=RootType.noun,
            description="",
        ),
        ModelRootResult(
            model="c",
            root_en="buyer",
            root_abbr="buy",
            root_type=RootType.noun,
            description="",
        ),
    ]
    final, auto = decide_root(results)
    assert auto is False
    assert final.decision_type == DecisionType.model_conflict
