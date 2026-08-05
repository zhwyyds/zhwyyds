from __future__ import annotations

from pathlib import Path

from data_governance.compare.roots import (
    build_comparison,
    decide_root,
    decision_to_source_model,
)
from data_governance.config_loader import load_models
from data_governance.io.reviews import next_review_path, now_iso_cn, write_root_review
from data_governance.io.roots_csv import append_root_row, make_root_csv_row
from data_governance.llm.env import resolve_use_mock
from data_governance.llm.factory import build_live_clients
from data_governance.llm.mock import clients_from_fixture, default_customer_fixture
from data_governance.llm.parallel import run_models_parallel_mock, run_models_parallel_prompt
from data_governance.parsing.root_generation import (
    RootResponseParseError,
    parse_root_generation_response,
    row_to_model_fields,
)
from data_governance.paths import repo_root
from data_governance.prompts.root_generation import build_root_generation_prompt
from data_governance.schemas.roots import (
    ModelRootResult,
    ReviewStatus,
    RootGenerationRequest,
    RootReviewDocument,
    RootReviewItem,
    SourceModel,
)


class RootGenerationPipeline:
    def __init__(
        self,
        *,
        base_dir: Path | None = None,
        use_mock: bool | None = None,
        fixture: dict | None = None,
    ) -> None:
        self.base_dir = base_dir or repo_root()
        self._use_mock = use_mock
        self.fixture = fixture or default_customer_fixture()

    def run(
        self,
        request: RootGenerationRequest,
        *,
        write_roots: bool = False,
    ) -> RootReviewDocument:
        models = load_models("root_generation", config_path=self.base_dir / "config" / "models.csv")
        model_names = [m.model_name for m in models]
        terms = request.terms
        prompt = build_root_generation_prompt(terms)
        use_mock = resolve_use_mock(self._use_mock)

        if use_mock:
            clients = clients_from_fixture(model_names, self.fixture)
            raw_by_model = run_models_parallel_mock(clients, terms)
        else:
            live_clients = build_live_clients(models)
            raw_by_model = run_models_parallel_prompt(live_clients, prompt, cache_base_dir=self.base_dir)

        items: list[RootReviewItem] = []
        for term in terms:
            model_results: list[ModelRootResult] = []
            for model_name, raw in raw_by_model:
                try:
                    rows = parse_root_generation_response(raw)
                except RootResponseParseError:
                    continue
                match = next((r for r in rows if r.get("cn_term") == term.cn_term), None)
                if match is None:
                    continue
                fields = row_to_model_fields(match)
                model_results.append(ModelRootResult(model=model_name, **fields))

            if len(model_results) < 2:
                raise RuntimeError(f"insufficient model results for {term.cn_term!r}")

            comparison = build_comparison(model_results)
            final, auto_approved = decide_root(model_results, comparison=comparison)
            items.append(
                RootReviewItem(
                    cn_term=term.cn_term,
                    context=term.context,
                    model_results=model_results,
                    comparison=comparison,
                    final_decision=final,
                    auto_approved=auto_approved,
                )
            )

        review_id = f"RR_{request.domain.upper()}_001"
        doc = RootReviewDocument(
            review_id=review_id,
            domain=request.domain,
            created_at=now_iso_cn(),
            models_used=model_names,
            items=items,
        )

        reviews_dir = self.base_dir / "reviews" / "root_reviews"
        out_path = next_review_path(reviews_dir, request.domain)
        write_root_review(doc, out_path)

        if write_roots:
            roots_dir = self.base_dir / "roots"
            for item in items:
                if not item.auto_approved:
                    continue
                sm = decision_to_source_model(item.final_decision.decision_type)
                if sm is None:
                    continue
                row = make_root_csv_row(
                    domain=request.domain,
                    root_cn=item.cn_term,
                    root_en=item.final_decision.root_en,
                    root_abbr=item.final_decision.root_abbr,
                    root_type=item.final_decision.root_type,
                    description=item.final_decision.description,
                    source_model=SourceModel(sm),
                    review_status=ReviewStatus.approved,
                    roots_dir=roots_dir,
                )
                append_root_row(
                    roots_dir / f"{request.domain}_roots.csv",
                    row,
                )

        return doc
