import json
from pathlib import Path

from data_governance.pipeline.root_generation import RootGenerationPipeline
from data_governance.schemas.roots import RootGenerationRequest, TermInput


def test_root_generate_customer_fixture(project_root: Path, tmp_path: Path):
    base = tmp_path / "proj"
    base.mkdir()
    for name in ("config", "reviews/root_reviews", "roots"):
        (base / name).mkdir(parents=True)
    (base / "config" / "models.csv").write_text(
        (project_root / "config" / "models.csv").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    req = RootGenerationRequest(domain="cust", terms=[TermInput(cn_term="客户", context="家居卖场")])
    pipe = RootGenerationPipeline(base_dir=base, use_mock=True)
    doc = pipe.run(req, write_roots=True)

    assert len(doc.items) == 1
    item = doc.items[0]
    assert item.auto_approved is True
    assert item.final_decision.root_abbr == "cust"

    reviews = list((base / "reviews" / "root_reviews").glob("cust_root_review_*.json"))
    assert len(reviews) == 1
    saved = json.loads(reviews[0].read_text(encoding="utf-8"))
    assert saved["items"][0]["final_decision"]["decision_type"] == "model_majority"

    csv_path = base / "roots" / "cust_roots.csv"
    assert csv_path.is_file()
    text = csv_path.read_text(encoding="utf-8")
    assert "R_CUST_001" in text
    assert "cust" in text
