from __future__ import annotations

from pathlib import Path

from data_governance.compare.metrics import build_metric_comparison, decide_metric
from data_governance.config_loader import load_models
from data_governance.io.metric_reviews import next_metric_review_path, write_metric_review
from data_governance.io.reviews import now_iso_cn
from data_governance.llm.env import resolve_use_mock
from data_governance.llm.factory import build_live_clients
from data_governance.llm.mock_metric import (
    default_monthly_sales_fixture,
    metric_clients_from_fixture,
)
from data_governance.llm.parallel import run_models_parallel_mock, run_models_parallel_prompt
from data_governance.parsing.metric_review import (
    MetricResponseParseError,
    parse_metric_review_response,
    row_to_metric_review_fields,
)
from data_governance.paths import repo_root
from data_governance.prompts.metric_review import build_metric_review_prompt
from data_governance.schemas.metrics import (
    MetricReviewDocument,
    MetricReviewItem,
    MetricReviewRequest,
    ModelMetricReview,
)


class MetricReviewPipeline:
    def __init__(
        self,
        *,
        base_dir: Path | None = None,
        use_mock: bool | None = None,
        fixture: dict | None = None,
    ) -> None:
        self.base_dir = base_dir or repo_root()
        self._use_mock = use_mock
        self.fixture = fixture or default_monthly_sales_fixture()

    def run(self, request: MetricReviewRequest) -> MetricReviewDocument:
        models = load_models("metric_review", config_path=self.base_dir / "config" / "models.csv")
        model_names = [m.model_name for m in models]
        metrics = request.metrics
        from data_governance.io.catalog import load_catalog
        from data_governance.roots.dictionary import (
            build_root_dictionary,
            dictionary_to_prompt_text,
        )

        root_text = ""
        try:
            catalog = load_catalog(self.base_dir)
            root_text = dictionary_to_prompt_text(build_root_dictionary(catalog.roots, domain=request.domain))
        except (FileNotFoundError, OSError, ValueError):
            root_text = ""  # 轻量项目无 catalog 时跳过词根字典注入
        prompt = build_metric_review_prompt(metrics, root_dictionary_text=root_text)
        use_mock = resolve_use_mock(self._use_mock)

        if use_mock:
            clients = metric_clients_from_fixture(model_names, self.fixture)
            raw_by_model = run_models_parallel_mock(clients, metrics)
        else:
            live_clients = build_live_clients(models)
            raw_by_model = run_models_parallel_prompt(live_clients, prompt, cache_base_dir=self.base_dir)

        items: list[MetricReviewItem] = []
        for metric in metrics:
            model_reviews: list[ModelMetricReview] = []
            for model_name, raw in raw_by_model:
                try:
                    rows = parse_metric_review_response(raw)
                except MetricResponseParseError:
                    continue
                match = next((r for r in rows if r.get("metric_id") == metric.metric_id), None)
                if match is None:
                    continue
                fields = row_to_metric_review_fields(match)
                model_reviews.append(ModelMetricReview(model=model_name, **fields))

            if len(model_reviews) < 1:
                raise RuntimeError(f"insufficient model reviews for {metric.metric_id!r}")

            comparison = build_metric_comparison(model_reviews)
            final = decide_metric(model_reviews)
            items.append(
                MetricReviewItem(
                    metric_id=metric.metric_id,
                    metric_en=metric.metric_en,
                    model_reviews=model_reviews,
                    comparison=comparison,
                    final_decision=final,
                )
            )

        doc = MetricReviewDocument(
            review_id=f"MR_{request.domain.upper()}_001",
            domain=request.domain,
            created_at=now_iso_cn(),
            models_used=model_names,
            items=items,
        )

        reviews_dir = self.base_dir / "reviews" / "metric_reviews"
        out_path = next_metric_review_path(reviews_dir, request.domain)
        write_metric_review(doc, out_path)
        return doc
