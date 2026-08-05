from pathlib import Path

import pytest

from data_governance.config_loader import load_domains, load_models
from data_governance.paths import repo_root


def test_load_domains_from_repo():
    root = repo_root(Path(__file__).resolve().parent.parent)
    domains = load_domains(root / "config" / "domains.csv")
    assert len(domains) == 14
    assert domains[0].domain_code == "cust"


def test_load_root_generation_models():
    root = repo_root(Path(__file__).resolve().parent.parent)
    models = load_models("root_generation", config_path=root / "config" / "models.csv")
    assert len(models) >= 3
    assert models[0].priority <= models[-1].priority
    assert models[0].api_key_env == "OPENAI_API_KEY"


def test_load_models_requires_min_two(tmp_path: Path):
    csv_path = tmp_path / "models.csv"
    csv_path.write_text(
        "model_id,model_name,provider,use_case,priority,enabled,api_endpoint,remark\n"
        "1,gpt-4o,OpenAI,root_generation,1,true,,\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="at least 2"):
        load_models("root_generation", config_path=csv_path)
